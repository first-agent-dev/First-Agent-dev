"""Compare GigaAM Q8_0 and Q4_K on identical local audio, with optional WER/CER."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

from ASR.pipeline import (
    DEFAULT_INBOX,
    DEFAULT_Q4_MODEL,
    DEFAULT_Q8_MODEL,
    DEFAULT_REFERENCES,
    DEFAULT_WORK,
    PipelineError,
    atomic_write_text,
    choose_vad,
    crispasr_version,
    exclusive_run_lock,
    find_audio_files,
    prepare_audio,
    resolve_crispasr_binary,
    resolve_model,
    run_inference,
    transcription_cache_key,
    utc_timestamp,
    validate_unique_audio_names,
)
from ASR.quality import character_error_rate, normalize_for_scoring, word_error_rate


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ожидается целое число") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("значение должно быть не меньше 1")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ожидается число") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("значение должно быть конечным числом больше 0")
    return parsed


def _non_negative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ожидается число") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("значение должно быть конечным числом не меньше 0")
    return parsed


def _default_threads() -> int:
    configured = os.environ.get("ASR_THREADS")
    if configured:
        try:
            return max(1, int(configured))
        except ValueError:
            return 4
    return min(4, os.cpu_count() or 1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Сравнить Q8_0 и Q4_K на одном аудио и, если есть эталон, измерить WER/CER."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INBOX, help="Папка с аудиофайлами")
    parser.add_argument("--audio", type=Path, action="append", help="Указать файл вручную; флаг можно повторить")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_INBOX.parent / "benchmarks")
    parser.add_argument("--reference-dir", type=Path, default=DEFAULT_REFERENCES)
    parser.add_argument(
        "--q8-model",
        type=Path,
        default=Path(os.environ.get("ASR_Q8_MODEL", str(DEFAULT_Q8_MODEL))),
        help="GGUF Q8_0 для e2e-RNNT",
    )
    parser.add_argument(
        "--q4-model",
        type=Path,
        default=Path(os.environ.get("ASR_Q4_MODEL", str(DEFAULT_Q4_MODEL))),
        help="GGUF Q4_K для e2e-RNNT",
    )
    parser.add_argument("--binary", default=os.environ.get("CRISPASR_BIN"), help="Путь к CrispASR")
    parser.add_argument("--threads", type=_positive_int, default=_default_threads())
    parser.add_argument("--repeats", type=_positive_int, default=3, help="Число прогонов каждой квантизации")
    parser.add_argument("--vad", choices=("auto", "on", "off"), default="auto")
    parser.add_argument("--vad-threshold", type=_positive_float, default=20.0)
    parser.add_argument(
        "--timeout", type=_non_negative_float, default=0, help="Таймаут одного запуска в секундах; 0 = без лимита"
    )
    parser.add_argument(
        "--conversion-timeout",
        type=_non_negative_float,
        default=0,
        help="Таймаут ffmpeg в секундах; 0 = без лимита",
    )
    return parser.parse_args()


def _host_info() -> dict[str, Any]:
    cpu_model = "unknown"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                cpu_model = line.split(":", maxsplit=1)[1].strip()
                break

    memory_gib: float | None = None
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        memory_gib = round(pages * page_size / (1024**3), 2)
    except (OSError, ValueError):
        pass

    return {
        "os": platform.platform(),
        "architecture": platform.machine(),
        "cpu_model": cpu_model,
        "logical_cpus": os.cpu_count(),
        "ram_gib": memory_gib,
        "python": platform.python_version(),
    }


def _files_to_process(args: argparse.Namespace) -> list[Path]:
    if args.audio:
        return [path.expanduser() for path in args.audio]
    return find_audio_files(args.input_dir.expanduser())


def _model_metrics(
    quant: str,
    model_path: Path,
    run_seconds: list[float],
    transcript: str,
    audio_seconds: float,
    preparation_seconds: float,
    reference_text: str | None,
    repeat_consistent: bool,
) -> dict[str, Any]:
    median_seconds = statistics.median(run_seconds)
    minimum_seconds = min(run_seconds)
    model_stat = model_path.stat()
    rtf = median_seconds / audio_seconds if audio_seconds > 0 else None
    realtime_multiplier = audio_seconds / median_seconds if median_seconds > 0 else None
    end_to_end_rtf = (median_seconds + preparation_seconds) / audio_seconds if audio_seconds > 0 else None
    wer = word_error_rate(reference_text, transcript) if reference_text is not None else None
    cer = character_error_rate(reference_text, transcript) if reference_text is not None else None
    return {
        "quantization": quant,
        "model_file": model_path.name,
        "model_size_bytes": model_stat.st_size,
        "model_mtime_ns": model_stat.st_mtime_ns,
        "run_seconds": [round(value, 4) for value in run_seconds],
        "median_inference_seconds": round(median_seconds, 4),
        "minimum_inference_seconds": round(minimum_seconds, 4),
        "preparation_seconds": round(preparation_seconds, 4),
        "real_time_factor": round(rtf, 6) if rtf is not None else None,
        "end_to_end_real_time_factor": round(end_to_end_rtf, 6) if end_to_end_rtf is not None else None,
        "times_real_time": round(realtime_multiplier, 6) if realtime_multiplier is not None else None,
        "wer": round(wer, 6) if wer is not None else None,
        "cer": round(cer, 6) if cer is not None else None,
        "repeat_consistent": repeat_consistent,
        "transcript": transcript,
    }


def _benchmark_one(
    source: Path,
    *,
    models: dict[str, Path],
    binary_path: Path,
    output_dir: Path,
    reference_dir: Path,
    work_dir: Path,
    threads: int,
    repeats: int,
    vad_mode: str,
    vad_threshold: float,
    timeout_seconds: float,
    conversion_timeout_seconds: float = 0,
    runtime_version: str = "unknown",
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    initial_input_keys = {
        quant: transcription_cache_key(
            source,
            model_path,
            binary_path,
            threads=threads,
            vad_mode=vad_mode,
            vad_threshold_seconds=vad_threshold,
        )
        for quant, model_path in models.items()
    }
    times = {quant: [] for quant in models}
    transcripts: dict[str, str] = {}
    normalized_transcripts: dict[str, list[str]] = {}
    repeat_consistent = dict.fromkeys(models, True)

    with tempfile.TemporaryDirectory(prefix="benchmark-", dir=work_dir) as temporary_dir:
        temporary_root = Path(temporary_dir)
        prepared = prepare_audio(
            source,
            temporary_root / "normalized.wav",
            timeout_seconds=conversion_timeout_seconds,
        )
        vad_enabled = choose_vad(vad_mode, prepared.duration_seconds, vad_threshold)
        for repeat_index in range(repeats):
            quant_order = list(models)
            if repeat_index % 2:
                quant_order.reverse()
            for quant in quant_order:
                result = run_inference(
                    prepared.path,
                    models[quant],
                    temporary_root / f"{quant}-run-{repeat_index + 1}",
                    threads=threads,
                    vad_enabled=vad_enabled,
                    binary_path=binary_path,
                    timeout_seconds=timeout_seconds,
                )
                times[quant].append(result.inference_seconds)
                normalized = normalize_for_scoring(result.transcript)
                if quant not in transcripts:
                    transcripts[quant] = result.transcript
                    normalized_transcripts[quant] = normalized
                elif normalized_transcripts[quant] != normalized:
                    repeat_consistent[quant] = False

    final_input_keys = {
        quant: transcription_cache_key(
            source,
            model_path,
            binary_path,
            threads=threads,
            vad_mode=vad_mode,
            vad_threshold_seconds=vad_threshold,
        )
        for quant, model_path in models.items()
    }
    if final_input_keys != initial_input_keys:
        raise PipelineError("Аудио, модель или runtime изменились во время benchmark; повторите замер.")

    reference_path = reference_dir / f"{source.stem}.txt"
    reference_text = None
    if reference_path.is_file():
        try:
            reference_text = reference_path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise PipelineError(f"Эталон должен быть в UTF-8: {reference_path}: {exc}") from exc
    model_results = {
        quant: _model_metrics(
            quant,
            models[quant],
            times[quant],
            transcripts[quant],
            prepared.duration_seconds,
            prepared.preparation_seconds,
            reference_text,
            repeat_consistent[quant],
        )
        for quant in models
    }
    q8_words = normalize_for_scoring(transcripts["q8_0"])
    q4_words = normalize_for_scoring(transcripts["q4_k"])
    agreement_wer = word_error_rate(transcripts["q8_0"], transcripts["q4_k"])
    source_stat = source.stat()
    report = {
        "schema_version": 1,
        "created_at_utc": utc_timestamp(),
        "source_file": source.name,
        "source_size_bytes": source_stat.st_size,
        "source_mtime_ns": source_stat.st_mtime_ns,
        "audio_duration_seconds": round(prepared.duration_seconds, 4),
        "reference_file": reference_path.name if reference_text is not None else None,
        "reference_available": reference_text is not None,
        "runtime": f"CrispASR {runtime_version}",
        "backend": "gigaam",
        "device": "cpu",
        "threads": threads,
        "repeats_per_model": repeats,
        "vad_mode": vad_mode,
        "vad_threshold_seconds": vad_threshold,
        "vad_enabled": vad_enabled,
        "host": _host_info(),
        "models": model_results,
        "quantization_comparison": {
            "q4_vs_q8_wer": round(agreement_wer, 6) if agreement_wer is not None else None,
            "normalized_transcripts_identical": q8_words == q4_words,
            "interpretation": "Q8/Q4 agreement is not an accuracy score; use a human reference for WER/CER.",
        },
    }
    base_name = source.name
    json_path = output_dir / f"{base_name}.benchmark.json"
    markdown_path = output_dir / f"{base_name}.benchmark.md"
    for quant, model_result in model_results.items():
        transcript_path = output_dir / f"{base_name}.{quant}.txt"
        atomic_write_text(transcript_path, model_result["transcript"].rstrip() + "\n")
    atomic_write_text(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(markdown_path, _format_report(report))
    return markdown_path, json_path


def _percent(value: float | None) -> str:
    return f"{value * 100:.2f}%" if value is not None else "—"


def _format_report(report: dict[str, Any]) -> str:
    reference_label = report["reference_file"] or "не задан (WER/CER не измерялись)"
    lines = [
        f"# Сравнение GigaAM: {report['source_file']}",
        "",
        f"- **Хост:** {report['host']['cpu_model']} ({report['host']['logical_cpus']} логических CPU)",
        f"- **ОЗУ:** {report['host']['ram_gib'] or 'н/д'} GiB",
        f"- **Runtime:** {report['runtime']}, CPU-only; потоков: {report['threads']}",
        f"- **Аудио:** {report['audio_duration_seconds']:.2f} с; "
        f"VAD: {'да' if report['vad_enabled'] else 'нет'} "
        f"(режим {report['vad_mode']}, порог auto {report['vad_threshold_seconds']:g} с)",
        f"- **Повторы:** {report['repeats_per_model']} на вариант; подготовка аудио: "
        f"{report['models']['q8_0']['preparation_seconds']:.2f} с (один раз)",
        f"- **Эталон:** `{reference_label}`",
        "",
        "## Результаты",
        "",
        "| Вариант | Модель | Размер | Медиана инференса | Мин. инференс | RTF* | Скорость | WER | CER |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for quant, result in report["models"].items():
        lines.append(
            f"| {quant} | `{result['model_file']}` | {result['model_size_bytes'] / 1000000:.0f} MB | "
            f"{result['median_inference_seconds']:.2f} с | {result['minimum_inference_seconds']:.2f} с | "
            f"{result['real_time_factor']:.3f} | {result['times_real_time']:.2f}× | "
            f"{_percent(result['wer'])} | {_percent(result['cer'])} |"
        )
    comparison = report["quantization_comparison"]
    lines.extend(
        [
            "",
            "`RTF = время инференса / длительность аудио`; меньше 1 — быстрее реального времени.",
            "Время включает запуск CLI и загрузку модели, но не однократное преобразование через ffmpeg.",
            "WER/CER сравниваются с эталоном; без эталона совпадение Q8/Q4 не означает точность.",
            "Нормализованный текст Q8 и Q4 совпал: "
            f"{'да' if comparison['normalized_transcripts_identical'] else 'нет'}.",
            f"WER Q4 относительно Q8 (только расхождение вариантов): {_percent(comparison['q4_vs_q8_wer'])}.",
            "",
            "## Транскрипты",
            "",
        ]
    )
    for quant, result in report["models"].items():
        lines.extend([f"### {quant}", "", result["transcript"] or "_(пустой транскрипт)_", ""])
    return "\n".join(lines)


def _run(args: argparse.Namespace) -> int:
    try:
        audio_files = _files_to_process(args)
        validate_unique_audio_names(audio_files)
        if not audio_files:
            print(f"В папке нет аудио для сравнения: {args.input_dir}")
            return 0
        models = {
            "q8_0": resolve_model(args.q8_model),
            "q4_k": resolve_model(args.q4_model),
        }
        binary_path = resolve_crispasr_binary(args.binary)
        runtime_version = crispasr_version(binary_path)
    except (OSError, PipelineError) as exc:
        print(f"Ошибка подготовки benchmark: {exc}", file=sys.stderr)
        return 2

    failures = 0
    output_dir = args.output_dir.expanduser().resolve()
    reference_dir = args.reference_dir.expanduser()
    for source in audio_files:
        try:
            print(f"START {source.name}: {args.repeats} повторов, CrispASR {runtime_version}", flush=True)
            markdown_path, json_path = _benchmark_one(
                source,
                models=models,
                binary_path=binary_path,
                output_dir=output_dir,
                reference_dir=reference_dir,
                work_dir=DEFAULT_WORK,
                threads=args.threads,
                repeats=args.repeats,
                vad_mode=args.vad,
                vad_threshold=args.vad_threshold,
                timeout_seconds=args.timeout,
                conversion_timeout_seconds=args.conversion_timeout,
                runtime_version=runtime_version,
            )
        except (OSError, PipelineError) as exc:
            failures += 1
            print(f"ERROR {source.name}: {exc}", file=sys.stderr)
            continue
        print(f"OK {source.name}: report={markdown_path}; data={json_path}")

    print(f"Benchmark завершён: файлов {len(audio_files) - failures}, ошибок {failures}")
    return 1 if failures else 0


def main() -> int:
    args = _parse_args()
    try:
        with exclusive_run_lock(DEFAULT_WORK / ".asr.lock"):
            return _run(args)
    except (OSError, PipelineError) as exc:
        print(f"Ошибка подготовки benchmark: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

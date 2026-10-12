"""One-shot folder runner: audio in ASR/data/inbox, Markdown + JSON out."""

from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile
from pathlib import Path

from ASR.pipeline import (
    DEFAULT_INBOX,
    DEFAULT_OUTBOX,
    DEFAULT_Q8_MODEL,
    DEFAULT_WORK,
    PipelineError,
    Transcription,
    choose_vad,
    crispasr_version,
    exclusive_run_lock,
    find_audio_files,
    prepare_audio,
    resolve_crispasr_binary,
    resolve_model,
    run_inference,
    transcription_cache_key,
    transcription_outputs_are_current,
    validate_unique_audio_names,
    write_transcription_files,
)


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
        description="Распознать аудио из папки и сохранить Markdown-транскрипт с метриками."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INBOX, help="Папка с исходными аудиофайлами")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTBOX, help="Папка для .md и .json")
    parser.add_argument(
        "--audio",
        type=Path,
        action="append",
        help="Обработать указанный файл вместо сканирования входной папки; можно повторить",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(os.environ.get("ASR_MODEL", str(DEFAULT_Q8_MODEL))),
        help="Локальный GGUF (по умолчанию GigaAM e2e-RNNT Q8_0)",
    )
    parser.add_argument(
        "--binary",
        default=os.environ.get("CRISPASR_BIN"),
        help="Путь к CrispASR; по умолчанию ищется установленный runtime или PATH",
    )
    parser.add_argument("--threads", type=_positive_int, default=_default_threads(), help="Потоки CPU, по умолчанию 4")
    parser.add_argument("--vad", choices=("auto", "on", "off"), default="auto", help="VAD для длинного аудио")
    parser.add_argument(
        "--vad-threshold",
        type=_positive_float,
        default=20.0,
        help="В режиме auto включать VAD при длительности больше N секунд (по умолчанию 20)",
    )
    parser.add_argument(
        "--timeout", type=_non_negative_float, default=0, help="Таймаут инференса в секундах; 0 = без лимита"
    )
    parser.add_argument(
        "--conversion-timeout",
        type=_non_negative_float,
        default=0,
        help="Таймаут ffmpeg в секундах; 0 = без лимита",
    )
    parser.add_argument("--force", action="store_true", help="Повторно обработать аудио даже при актуальном результате")
    return parser.parse_args()


def _files_to_process(args: argparse.Namespace) -> list[Path]:
    if args.audio:
        return [path.expanduser() for path in args.audio]
    return find_audio_files(args.input_dir.expanduser())


def _process_one(
    source: Path,
    *,
    model_path: Path,
    binary_path: Path,
    output_dir: Path,
    work_dir: Path,
    threads: int,
    vad_mode: str,
    vad_threshold: float,
    timeout_seconds: float,
    conversion_timeout_seconds: float,
    runtime_version: str,
) -> tuple[Path, Path, Transcription]:
    cache_key = transcription_cache_key(
        source,
        model_path,
        binary_path,
        threads=threads,
        vad_mode=vad_mode,
        vad_threshold_seconds=vad_threshold,
    )
    with tempfile.TemporaryDirectory(prefix="transcribe-", dir=work_dir) as temporary_dir:
        temporary_root = Path(temporary_dir)
        prepared = prepare_audio(
            source,
            temporary_root / "normalized.wav",
            timeout_seconds=conversion_timeout_seconds,
        )
        vad_enabled = choose_vad(vad_mode, prepared.duration_seconds, vad_threshold)
        inference = run_inference(
            prepared.path,
            model_path,
            temporary_root / "result",
            threads=threads,
            vad_enabled=vad_enabled,
            binary_path=binary_path,
            timeout_seconds=timeout_seconds,
        )
        final_cache_key = transcription_cache_key(
            source,
            model_path,
            binary_path,
            threads=threads,
            vad_mode=vad_mode,
            vad_threshold_seconds=vad_threshold,
        )
        if final_cache_key != cache_key:
            raise PipelineError("Аудио, модель или runtime изменились во время обработки; повторите запуск.")
        result = Transcription(
            source=source.expanduser().absolute(),
            model=model_path,
            transcript=inference.transcript,
            audio_seconds=prepared.duration_seconds,
            preparation_seconds=prepared.preparation_seconds,
            inference_seconds=inference.inference_seconds,
            threads=threads,
            vad_enabled=vad_enabled,
            runtime_version=runtime_version,
            runtime_binary=binary_path,
            vad_mode=vad_mode,
            vad_threshold_seconds=vad_threshold,
            cache_key=cache_key,
        )
        markdown_path, json_path = write_transcription_files(result, output_dir)
    return markdown_path, json_path, result


def _run(args: argparse.Namespace) -> int:
    try:
        audio_files = _files_to_process(args)
        validate_unique_audio_names(audio_files)
    except PipelineError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    if not audio_files:
        print(f"В папке нет аудио для обработки: {args.input_dir}")
        return 0

    output_dir = args.output_dir.expanduser().resolve()
    work_dir = DEFAULT_WORK
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        model_path = resolve_model(args.model)
        binary_path = resolve_crispasr_binary(args.binary)
        runtime_version = crispasr_version(binary_path)
    except (OSError, PipelineError) as exc:
        print(f"Ошибка подготовки ASR: {exc}", file=sys.stderr)
        return 2

    failures = 0
    processed = 0
    for source in audio_files:
        try:
            if not args.force and transcription_outputs_are_current(
                source,
                model_path,
                binary_path,
                output_dir,
                threads=args.threads,
                vad_mode=args.vad,
                vad_threshold_seconds=args.vad_threshold,
            ):
                print(f"SKIP {source.name}: входы и настройки не изменились (--force для повтора)")
                continue
            print(f"START {source.name}: CrispASR {runtime_version}, {args.threads} потоков", flush=True)
            markdown_path, json_path, result = _process_one(
                source,
                model_path=model_path,
                binary_path=binary_path,
                output_dir=output_dir,
                work_dir=work_dir,
                threads=args.threads,
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
        processed += 1
        speed = result.audio_seconds / result.inference_seconds if result.inference_seconds > 0 else 0
        print(f"OK {source.name}: {speed:.2f}x realtime; transcript={markdown_path}; metrics={json_path}")

    print(f"Готово: обработано {processed}, ошибок {failures}")
    return 1 if failures else 0


def main() -> int:
    args = _parse_args()
    try:
        with exclusive_run_lock(DEFAULT_WORK / ".asr.lock"):
            return _run(args)
    except (OSError, PipelineError) as exc:
        print(f"Ошибка подготовки ASR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

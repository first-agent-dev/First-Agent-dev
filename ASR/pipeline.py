"""Small, dependency-free adapter from audio files to GigaAM/CrispASR."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import wave
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ASR_DIR = Path(__file__).resolve().parent
DATA_DIR = ASR_DIR / "data"
DEFAULT_INBOX = DATA_DIR / "inbox"
DEFAULT_OUTBOX = DATA_DIR / "outbox"
DEFAULT_REFERENCES = DATA_DIR / "references"
DEFAULT_WORK = DATA_DIR / "work"
DEFAULT_Q8_MODEL = ASR_DIR / "models" / "gigaam-v3-e2e-rnnt-q8_0.gguf"
DEFAULT_Q4_MODEL = ASR_DIR / "models" / "gigaam-v3-e2e-rnnt-q4_k.gguf"
CRISPASR_VERSION = "v0.8.43"
TRANSCRIPTION_SCHEMA_VERSION = 2
SUPPORTED_AUDIO_EXTENSIONS = frozenset(
    {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".oga", ".opus", ".aac", ".webm", ".mp4"}
)


class PipelineError(RuntimeError):
    """An actionable error from audio preparation or ASR inference."""


@dataclass(frozen=True)
class PreparedAudio:
    path: Path
    duration_seconds: float
    preparation_seconds: float


@dataclass(frozen=True)
class InferenceResult:
    transcript: str
    inference_seconds: float


@dataclass(frozen=True)
class Transcription:
    source: Path
    model: Path
    transcript: str
    audio_seconds: float
    preparation_seconds: float
    inference_seconds: float
    threads: int
    vad_enabled: bool
    runtime_version: str = "unknown"
    runtime_binary: Path | None = None
    vad_mode: str = "auto"
    vad_threshold_seconds: float = 20.0
    cache_key: str | None = None


def find_audio_files(input_dir: Path) -> list[Path]:
    """List supported audio files in one folder, in stable name order."""
    if not input_dir.is_dir():
        raise PipelineError(f"Папка входа не найдена: {input_dir}\nСоздайте её или выполните: ./ASR/asr setup")
    return sorted(
        (
            path
            for path in input_dir.iterdir()
            if path.is_file() and not path.name.startswith(".") and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def validate_unique_audio_names(files: list[Path]) -> None:
    """Reject colliding output names and control characters before writing artifacts."""
    seen: dict[str, Path] = {}
    for source in files:
        if any(unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"} for character in source.name):
            raise PipelineError(f"Имя аудиофайла содержит управляющий символ: {source!r}")
        key = source.name.casefold()
        previous = seen.get(key)
        if previous is not None:
            raise PipelineError(
                f"Имена файлов конфликтуют в папке результатов: {previous} и {source}. "
                "Задайте им разные имена перед запуском."
            )
        seen[key] = source


def resolve_crispasr_binary(requested: str | Path | None = None) -> Path:
    """Resolve an explicit binary, the selected local install, or PATH."""
    selected = requested or os.environ.get("CRISPASR_BIN")
    if selected:
        selected_text = str(selected)
        candidate = Path(selected_text).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
        located = shutil.which(selected_text)
        if located:
            return Path(located).resolve()
        raise PipelineError(f"Не найден исполняемый CrispASR: {selected_text}")

    runtime_root = ASR_DIR / "runtime"
    current_file = runtime_root / ".current"
    if current_file.is_file():
        selected_version = current_file.read_text(encoding="ascii", errors="ignore").strip()
        if re.fullmatch(r"v[0-9]+(?:\.[0-9]+){2}", selected_version):
            selected_dir = runtime_root / selected_version
            if selected_dir.is_dir():
                candidates = sorted(selected_dir.rglob("crispasr"))
                for candidate in candidates:
                    if candidate.is_file() and os.access(candidate, os.X_OK):
                        return candidate.resolve()

    pinned_dir = runtime_root / CRISPASR_VERSION
    for runtime_dir in (pinned_dir, *sorted(runtime_root.glob("v*"), reverse=True)):
        if runtime_dir.is_dir():
            candidates = sorted(runtime_dir.rglob("crispasr"))
            for candidate in candidates:
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return candidate.resolve()

    located = shutil.which("crispasr")
    if located:
        return Path(located).resolve()

    raise PipelineError("CrispASR не установлен. Сначала выполните: ./ASR/asr setup")


def crispasr_version(binary_path: str | Path) -> str:
    """Read the actual installed runtime version; unknown is non-fatal for custom builds."""
    try:
        completed = subprocess.run(
            [str(binary_path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    for line in output.splitlines():
        if "version" in line.casefold() and ":" in line:
            return line.split(":", maxsplit=1)[1].strip() or "unknown"
    return output.splitlines()[0][:160] if output else "unknown"


@contextmanager
def exclusive_run_lock(lock_path: Path) -> Iterator[None]:
    """Serialize local inference and benchmarks so concurrent jobs cannot race."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PipelineError("Другой ASR run/benchmark уже выполняется; дождитесь его завершения.") from exc
        try:
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(f"pid={os.getpid()}\n")
            lock_file.flush()
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def resolve_model(requested: str | Path) -> Path:
    """Expand and validate a local GGUF model path."""
    model = Path(requested).expanduser()
    if not model.is_file():
        raise PipelineError(f"Файл модели не найден: {model}\nСначала выполните: ./ASR/asr setup")
    try:
        with model.open("rb") as handle:
            magic = handle.read(4)
    except OSError as exc:
        raise PipelineError(f"Не удалось прочитать модель {model}: {exc}") from exc
    if magic != b"GGUF":
        raise PipelineError(f"Файл не имеет сигнатуры GGUF: {model}")
    return model.resolve()


def find_ffmpeg(requested: str | Path | None = None) -> Path:
    """Resolve ffmpeg without introducing a Python media dependency."""
    selected = requested or os.environ.get("FFMPEG_BIN") or "ffmpeg"
    candidate = Path(selected).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate.resolve()
    located = shutil.which(str(selected))
    if located:
        return Path(located).resolve()
    raise PipelineError("Не найден ffmpeg. Установите его командой: sudo apt install ffmpeg")


def _tail(text: str, line_count: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-line_count:])


def _compatible_wav_duration(source: Path) -> float | None:
    """Return duration for a WAV already matching GigaAM's PCM input contract."""
    if source.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(source), "rb") as audio:
            if (
                audio.getnchannels() != 1
                or audio.getframerate() != 16000
                or audio.getsampwidth() != 2
                or audio.getcomptype() != "NONE"
            ):
                return None
            duration_seconds = audio.getnframes() / audio.getframerate()
    except (EOFError, OSError, wave.Error):
        return None
    return duration_seconds if duration_seconds > 0 else None


def prepare_audio(
    source: Path,
    destination: Path,
    *,
    ffmpeg_binary: str | Path | None = None,
    timeout_seconds: float = 0,
) -> PreparedAudio:
    """Convert input to the model's expected 16 kHz, mono, signed-16-bit WAV."""
    source = source.expanduser()
    destination = destination.expanduser()
    if not math.isfinite(timeout_seconds) or timeout_seconds < 0:
        raise PipelineError("Таймаут преобразования должен быть конечным числом не меньше 0")
    if not source.is_file():
        raise PipelineError(f"Аудиофайл не найден: {source}")
    if source.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise PipelineError(f"Неподдерживаемый формат {source.suffix!r}: {source.name}")
    compatible_duration = _compatible_wav_duration(source)
    if compatible_duration is not None:
        return PreparedAudio(source.resolve(), compatible_duration, 0.0)

    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg(ffmpeg_binary)
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(source.resolve()),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-f",
        "wav",
        str(destination.resolve()),
    ]

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds if timeout_seconds > 0 else None,
        )
    except subprocess.TimeoutExpired as exc:
        detail = exc.stderr or exc.stdout or ""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        suffix = f"\n{_tail(detail)}" if detail else ""
        raise PipelineError(f"ffmpeg превысил таймаут ({timeout_seconds:g} с){suffix}") from exc
    except OSError as exc:
        raise PipelineError(f"Не удалось запустить ffmpeg: {exc}") from exc
    preparation_seconds = time.perf_counter() - started

    if completed.returncode != 0:
        detail = _tail(completed.stderr or completed.stdout)
        suffix = f"\n{detail}" if detail else ""
        raise PipelineError(f"ffmpeg завершился с кодом {completed.returncode}: {source.name}{suffix}")
    if not destination.is_file() or destination.stat().st_size <= 44:
        raise PipelineError(f"ffmpeg не создал корректный WAV для {source.name}")

    duration_seconds = _compatible_wav_duration(destination)
    if duration_seconds is None:
        raise PipelineError(
            f"ffmpeg создал WAV, не соответствующий контракту GigaAM (16 kHz, mono, PCM16): {destination}"
        )
    return PreparedAudio(destination.resolve(), duration_seconds, preparation_seconds)


def choose_vad(mode: str, duration_seconds: float, threshold_seconds: float = 20.0) -> bool:
    """Use VAD for long clips to stay within GigaAM's practical attention window."""
    if not math.isfinite(threshold_seconds) or threshold_seconds <= 0:
        raise PipelineError("Порог VAD должен быть конечным числом больше 0")
    if mode == "on":
        return True
    if mode == "off":
        return False
    if mode == "auto":
        return duration_seconds > threshold_seconds
    raise PipelineError(f"Неизвестный режим VAD: {mode!r}")


def run_inference(
    audio_path: Path,
    model_path: Path,
    output_prefix: Path,
    *,
    threads: int,
    vad_enabled: bool,
    binary_path: str | Path | None = None,
    timeout_seconds: float = 0,
) -> InferenceResult:
    """Run one CPU inference and read CrispASR's plain-text output file."""
    if threads < 1:
        raise PipelineError("Число потоков должно быть не меньше 1")
    if not math.isfinite(timeout_seconds) or timeout_seconds < 0:
        raise PipelineError("Таймаут должен быть конечным числом не меньше 0")
    binary = resolve_crispasr_binary(binary_path)
    model = resolve_model(model_path)
    audio = audio_path.expanduser().resolve()
    if not audio.is_file():
        raise PipelineError(f"Подготовленный WAV не найден: {audio}")

    output_prefix = output_prefix.expanduser().resolve()
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    transcript_path = Path(f"{output_prefix}.txt")
    transcript_path.unlink(missing_ok=True)

    command = [
        str(binary),
        "--backend",
        "gigaam",
        "--model",
        str(model),
        "--file",
        str(audio),
        "--language",
        "ru",
        "--threads",
        str(threads),
        "--no-gpu",
        "-otxt",
        "-of",
        str(output_prefix),
    ]
    if vad_enabled:
        command.append("--vad")

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds if timeout_seconds > 0 else None,
        )
    except subprocess.TimeoutExpired as exc:
        detail = exc.stderr or exc.stdout or ""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        suffix = f"\n{_tail(detail)}" if detail else ""
        raise PipelineError(f"CrispASR превысил таймаут ({timeout_seconds:g} с){suffix}") from exc
    except OSError as exc:
        raise PipelineError(f"Не удалось запустить CrispASR: {exc}") from exc
    inference_seconds = time.perf_counter() - started

    if completed.returncode != 0:
        detail = _tail(completed.stderr or completed.stdout)
        suffix = f"\n{detail}" if detail else ""
        raise PipelineError(f"CrispASR завершился с кодом {completed.returncode}{suffix}")
    if not transcript_path.is_file():
        detail = _tail(completed.stderr or completed.stdout)
        suffix = f"\n{detail}" if detail else ""
        raise PipelineError(f"CrispASR не создал ожидаемый файл {transcript_path}{suffix}")

    try:
        transcript = transcript_path.read_text(encoding="utf-8").strip()
    except UnicodeError as exc:
        raise PipelineError(f"CrispASR создал невалидный UTF-8 транскрипт {transcript_path}: {exc}") from exc
    except OSError as exc:
        raise PipelineError(f"Не удалось прочитать транскрипт {transcript_path}: {exc}") from exc
    return InferenceResult(transcript, inference_seconds)


def _model_quant(model: Path) -> str:
    lowered = model.name.casefold()
    if "q8_0" in lowered:
        return "Q8_0"
    if "q4_k" in lowered:
        return "Q4_K"
    if "f16" in lowered:
        return "F16"
    return "unknown"


def _file_identity(path: Path) -> dict[str, int | str]:
    resolved = path.expanduser().resolve()
    stat = resolved.stat()
    return {"path": str(resolved), "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def transcription_cache_key(
    source: Path,
    model: Path,
    binary: Path,
    *,
    threads: int,
    vad_mode: str,
    vad_threshold_seconds: float,
) -> str:
    """Bind cached output to the source, model, runtime binary, and transcription settings."""
    identity = {
        "schema_version": TRANSCRIPTION_SCHEMA_VERSION,
        "source": _file_identity(source),
        "model": _file_identity(model),
        "runtime_binary": _file_identity(binary),
        "settings": {
            "threads": threads,
            "vad_mode": vad_mode,
            "vad_threshold_seconds": vad_threshold_seconds,
            "backend": "gigaam",
            "device": "cpu",
        },
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def transcription_outputs_are_current(
    source: Path,
    model: Path,
    binary: Path,
    output_dir: Path,
    *,
    threads: int,
    vad_mode: str,
    vad_threshold_seconds: float,
) -> bool:
    """Return true only when both outputs match the current inputs and processing settings."""
    markdown_path = output_dir / f"{source.name}.md"
    json_path = output_dir / f"{source.name}.json"
    if not markdown_path.is_file() or not json_path.is_file():
        return False
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != TRANSCRIPTION_SCHEMA_VERSION:
            return False
        expected_key = transcription_cache_key(
            source,
            model,
            binary,
            threads=threads,
            vad_mode=vad_mode,
            vad_threshold_seconds=vad_threshold_seconds,
        )
        if payload.get("cache_key") != expected_key:
            return False
        markdown_digest = hashlib.sha256(markdown_path.read_bytes()).hexdigest()
    except (OSError, UnicodeError, ValueError, TypeError):
        return False
    return payload.get("markdown_sha256") == markdown_digest


def _realtime_metrics(audio_seconds: float, inference_seconds: float) -> tuple[float | None, float | None]:
    if audio_seconds <= 0 or inference_seconds <= 0:
        return None, None
    return inference_seconds / audio_seconds, audio_seconds / inference_seconds


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp for machine-readable reports."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_write_text(path: Path, content: str) -> None:
    """Write a text artifact atomically so interrupted runs don't leave partial files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _format_seconds(seconds: float) -> str:
    if seconds >= 3600:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remainder = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{remainder:05.2f}"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes:02d}:{remainder:05.2f}"


def write_transcription_files(result: Transcription, output_dir: Path) -> tuple[Path, Path]:
    """Write a readable Markdown transcript and a JSON record with timings."""
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / f"{result.source.name}.md"
    json_path = output_dir / f"{result.source.name}.json"
    rtf, realtime_multiplier = _realtime_metrics(result.audio_seconds, result.inference_seconds)
    total_seconds = result.preparation_seconds + result.inference_seconds
    timestamp = utc_timestamp()
    transcript_body = result.transcript or "_(распознанная речь не найдена)_"
    source_stat = result.source.stat()
    model_stat = result.model.stat()
    binary_stat = result.runtime_binary.stat() if result.runtime_binary is not None else None
    cache_key = result.cache_key
    if cache_key is None and result.runtime_binary is not None:
        cache_key = transcription_cache_key(
            result.source,
            result.model,
            result.runtime_binary,
            threads=result.threads,
            vad_mode=result.vad_mode,
            vad_threshold_seconds=result.vad_threshold_seconds,
        )
    runtime_label = f"CrispASR {result.runtime_version}"
    markdown = "\n".join(
        [
            f"# Расшифровка: {result.source.name}",
            "",
            f"- **Модель:** GigaAM-v3, {_model_quant(result.model)} (`{result.model.name}`)",
            f"- **Рантайм:** {runtime_label}, CPU-only",
            f"- **Длительность аудио:** {_format_seconds(result.audio_seconds)}",
            f"- **Инференс:** {result.inference_seconds:.2f} с",
            f"- **Подготовка аудио:** {result.preparation_seconds:.2f} с",
            f"- **Всего:** {total_seconds:.2f} с",
            f"- **RTF:** {rtf:.3f}" if rtf is not None else "- **RTF:** н/д",
            (
                f"- **Скорость:** {realtime_multiplier:.2f}× реального времени"
                if realtime_multiplier is not None
                else "- **Скорость:** н/д"
            ),
            f"- **Потоки CPU:** {result.threads}",
            f"- **VAD:** {'да' if result.vad_enabled else 'нет'} "
            f"(режим {result.vad_mode}, порог auto {result.vad_threshold_seconds:g} с)",
            f"- **Обработано (UTC):** {timestamp}",
            "",
            "## Текст",
            "",
            transcript_body,
            "",
        ]
    )
    markdown_digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    payload = {
        "schema_version": TRANSCRIPTION_SCHEMA_VERSION,
        "source_file": result.source.name,
        "audio_duration_seconds": round(result.audio_seconds, 4),
        "backend": "gigaam",
        "model_file": result.model.name,
        "quantization": _model_quant(result.model),
        "runtime": runtime_label,
        "device": "cpu",
        "threads": result.threads,
        "vad_mode": result.vad_mode,
        "vad_threshold_seconds": result.vad_threshold_seconds,
        "vad_enabled": result.vad_enabled,
        "source_size_bytes": source_stat.st_size,
        "source_mtime_ns": source_stat.st_mtime_ns,
        "model_size_bytes": model_stat.st_size,
        "model_mtime_ns": model_stat.st_mtime_ns,
        "runtime_binary_size_bytes": binary_stat.st_size if binary_stat is not None else None,
        "runtime_binary_mtime_ns": binary_stat.st_mtime_ns if binary_stat is not None else None,
        "cache_key": cache_key,
        "markdown_sha256": markdown_digest,
        "preparation_seconds": round(result.preparation_seconds, 4),
        "inference_wall_seconds": round(result.inference_seconds, 4),
        "total_wall_seconds": round(total_seconds, 4),
        "real_time_factor": round(rtf, 6) if rtf is not None else None,
        "times_real_time": round(realtime_multiplier, 6) if realtime_multiplier is not None else None,
        "transcribed_at_utc": timestamp,
        "transcript": result.transcript,
    }
    atomic_write_text(markdown_path, markdown)
    atomic_write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return markdown_path, json_path

#!/usr/bin/env bash
# Install the pinned CPU runtime and both GigaAM e2e-RNNT quantizations.
set -Eeuo pipefail

ASR_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
DEFAULT_GIGAAM_REVISION="5df03d88f87f66ab6afc17c615370d20cda93669"
CRISPASR_VERSION="${CRISPASR_VERSION:-v0.8.43}"
CRISPASR_SHA256="${CRISPASR_SHA256:-}"
CRISPASR_SHA256="${CRISPASR_SHA256,,}"
GIGAAM_REVISION="${GIGAAM_REVISION:-$DEFAULT_GIGAAM_REVISION}"
GIGAAM_REVISION="${GIGAAM_REVISION,,}"
GIGAAM_Q8_SHA256="${GIGAAM_Q8_SHA256:-}"
GIGAAM_Q8_SHA256="${GIGAAM_Q8_SHA256,,}"
GIGAAM_Q4_SHA256="${GIGAAM_Q4_SHA256:-}"
GIGAAM_Q4_SHA256="${GIGAAM_Q4_SHA256,,}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat <<'EOF'
Установка локального ASR runtime и моделей.

Настройки через окружение:
  CRISPASR_VERSION=v0.8.43
  CRISPASR_SHA256=<sha256 для версии, отличной от v0.8.43>
  GIGAAM_REVISION=<HF commit SHA>
  GIGAAM_Q8_SHA256=<официальный SHA256 Q8_0 для альтернативной revision>
  GIGAAM_Q4_SHA256=<официальный SHA256 Q4_K для альтернативной revision>
  FFMPEG_BIN=/path/to/ffmpeg

Для revision, отличной от закреплённой, укажите оба хеша моделей.
Зависимости Ubuntu: curl, tar, Python >=3.11, sha256sum и flock.
ffmpeg нужен только для аудио, отличного от mono PCM16 WAV 16 kHz.
EOF
    exit 0
fi
if [[ $# -gt 0 ]]; then
    echo "Неизвестные параметры: $* (используйте --help)" >&2
    exit 2
fi

if [[ ! "$CRISPASR_VERSION" =~ ^v[0-9]+(\.[0-9]+){2}$ ]]; then
    echo "Неверная версия CrispASR: $CRISPASR_VERSION" >&2
    exit 2
fi
if [[ ! "$GIGAAM_REVISION" =~ ^[[:xdigit:]]{40}$ ]]; then
    echo "GIGAAM_REVISION должен быть 40-значным commit SHA Hugging Face." >&2
    exit 2
fi
if [[ -n "$CRISPASR_SHA256" && ! "$CRISPASR_SHA256" =~ ^[[:xdigit:]]{64}$ ]]; then
    echo "CRISPASR_SHA256 должен содержать 64 шестнадцатеричных символа." >&2
    exit 2
fi
for model_hash in "$GIGAAM_Q8_SHA256" "$GIGAAM_Q4_SHA256"; do
    if [[ -n "$model_hash" && ! "$model_hash" =~ ^[[:xdigit:]]{64}$ ]]; then
        echo "GIGAAM_Q8_SHA256/GIGAAM_Q4_SHA256 должны содержать 64 шестнадцатеричных символа." >&2
        exit 2
    fi
done

for dependency in curl tar python3 sha256sum flock; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        echo "Не найдена команда '$dependency'. Установите curl, tar, python3 и util-linux." >&2
        exit 2
    fi
done
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "Для ASR-скриптов нужен Python 3.11 или новее." >&2
    exit 2
fi
ffmpeg_command="${FFMPEG_BIN:-ffmpeg}"
if ! command -v "$ffmpeg_command" >/dev/null 2>&1 && [[ ! -x "$ffmpeg_command" ]]; then
    echo "Примечание: ffmpeg не найден; для преобразования MP3/FLAC и несовместимых WAV установите ffmpeg." >&2
fi

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Установщик CrispASR подготовлен только для Linux." >&2
    exit 2
fi

case "$(uname -m)" in
    x86_64|amd64)
        cpu_flags="$(awk -F: '/^flags/{print $2; exit}' /proc/cpuinfo 2>/dev/null || true)"
        if [[ " $cpu_flags " == *" avx2 "* && " $cpu_flags " == *" fma "* ]]; then
            runtime_asset="crispasr-linux-x86_64.tar.gz"
        else
            runtime_asset="crispasr-linux-x86_64-cpu-legacy.tar.gz"
            echo "AVX2/FMA не обнаружены: устанавливается совместимая, но более медленная CPU-сборка." >&2
        fi
        ;;
    *)
        echo "Этот экспериментальный установщик подготовлен для Linux x86_64, обнаружено: $(uname -m)" >&2
        exit 2
        ;;
esac

runtime_dir="$ASR_DIR/runtime/$CRISPASR_VERSION"
if [[ ! -d "$runtime_dir" ]]; then
    # GitHub's published asset digests for the pinned v0.8.43 release.
    case "$CRISPASR_VERSION/$runtime_asset" in
        v0.8.43/crispasr-linux-x86_64.tar.gz)
            pinned_sha256="e81b597cb80e49d8687a4bceb1eb24bf55928c55ff1292a9cde12e9b4fe0eb57"
            ;;
        v0.8.43/crispasr-linux-x86_64-cpu-legacy.tar.gz)
            pinned_sha256="c00f01bf6395fe0b6aa6b6b8313f8da7a434768a5bdb292a63bcb549d8ff77b0"
            ;;
        *)
            pinned_sha256="$CRISPASR_SHA256"
            ;;
    esac
    if [[ -z "$pinned_sha256" ]]; then
        echo "Нет закреплённого SHA256 для $CRISPASR_VERSION/$runtime_asset. "\
            "Передайте CRISPASR_SHA256=<официальный SHA256 релизного архива>." >&2
        exit 2
    fi
fi

# Published Hugging Face SHA256 values at DEFAULT_GIGAAM_REVISION.
pinned_q8_sha256="3aa25ce8a3e8ea9ebc66fc1f1a650a8d515f85c1846c76aaba1af84c1ded56b0"
pinned_q4_sha256="d7ce1f45afa7b6abf3462310c06d1ace1b017cb0c26e99a9cc9099c9b8e45d6d"
if [[ "$GIGAAM_REVISION" == "$DEFAULT_GIGAAM_REVISION" ]]; then
    expected_q8_sha256="${GIGAAM_Q8_SHA256:-$pinned_q8_sha256}"
    expected_q4_sha256="${GIGAAM_Q4_SHA256:-$pinned_q4_sha256}"
else
    expected_q8_sha256="$GIGAAM_Q8_SHA256"
    expected_q4_sha256="$GIGAAM_Q4_SHA256"
fi
if [[ -z "$expected_q8_sha256" || -z "$expected_q4_sha256" ]]; then
    echo "Для GIGAAM_REVISION=$GIGAAM_REVISION нужны оба официальных хеша: GIGAAM_Q8_SHA256 и GIGAAM_Q4_SHA256." >&2
    exit 2
fi

mkdir -p "$ASR_DIR/runtime" "$ASR_DIR/models" \
    "$ASR_DIR/data/inbox" "$ASR_DIR/data/outbox" "$ASR_DIR/data/references" "$ASR_DIR/data/work"
exec 9>"$ASR_DIR/.setup.lock"
if ! flock -n 9; then
    echo "Установщик ASR уже выполняется в другом процессе." >&2
    exit 1
fi
exec 8>"$ASR_DIR/data/work/.asr.lock"
if ! flock -n 8; then
    echo "ASR run/benchmark уже выполняется; дождитесь его завершения перед setup." >&2
    exit 1
fi
TEMP_DIR="$(mktemp -d "$ASR_DIR/.setup.XXXXXX")"
trap 'rm -rf -- "$TEMP_DIR"' EXIT

if [[ -d "$runtime_dir" ]]; then
    if find "$runtime_dir" -type f -name crispasr -executable -print -quit | grep -q .; then
        echo "CrispASR $CRISPASR_VERSION уже распакован: $runtime_dir"
    else
        echo "Найдена неполная установка $runtime_dir. Удалите только эту папку и повторите setup." >&2
        exit 1
    fi
else
    archive="$TEMP_DIR/$runtime_asset"
    extract_dir="$TEMP_DIR/runtime"
    runtime_url="https://github.com/CrispStrobe/CrispASR/releases/download/$CRISPASR_VERSION/$runtime_asset"
    mkdir -p "$extract_dir"
    echo "Скачиваю CrispASR $CRISPASR_VERSION ($runtime_asset)..."
    curl --fail --location --show-error --retry 3 --retry-all-errors \
        --connect-timeout 20 --max-time 600 --output "$archive" "$runtime_url"
    actual_sha256="$(sha256sum "$archive" | awk '{print $1}')"
    if [[ "$actual_sha256" != "$pinned_sha256" ]]; then
        echo "SHA256 CrispASR не совпал: ожидался $pinned_sha256, получен $actual_sha256" >&2
        exit 1
    fi
    if ! tar -tzf "$archive" > "$TEMP_DIR/archive.list"; then
        echo "Не удалось прочитать архив CrispASR: $runtime_url" >&2
        exit 1
    fi
    while IFS= read -r archive_entry; do
        if [[ "$archive_entry" == /* || "$archive_entry" == ".." || "$archive_entry" == ../* \
            || "$archive_entry" == */../* || "$archive_entry" == */.. ]]; then
            echo "В архиве обнаружен небезопасный путь: $archive_entry" >&2
            exit 1
        fi
    done < "$TEMP_DIR/archive.list"
    tar --extract --gzip --file="$archive" --directory="$extract_dir" --no-same-owner --no-same-permissions
    if ! find "$extract_dir" -type f -name crispasr -executable -print -quit | grep -q .; then
        echo "В архиве не найден исполняемый crispasr: $runtime_url" >&2
        exit 1
    fi
    mv "$extract_dir" "$runtime_dir"
fi

crispasr_bin="$(find "$runtime_dir" -type f -name crispasr -executable -print -quit)"
if [[ -z "$crispasr_bin" ]]; then
    echo "Не удалось определить путь к crispasr в $runtime_dir" >&2
    exit 1
fi

_download_model() {
    local filename="$1"
    local minimum_bytes="$2"
    local expected_sha256="$3"
    local destination="$ASR_DIR/models/$filename"
    local manifest="$destination.manifest"
    local temporary_file="$TEMP_DIR/$filename"
    local model_url="https://huggingface.co/cstr/gigaam-v3-GGUF/resolve/$GIGAAM_REVISION/$filename"

    if [[ -L "$destination" || ( -e "$destination" && ! -f "$destination" ) ]]; then
        echo "Путь модели должен быть обычным файлом, не ссылкой или каталогом: $destination" >&2
        return 1
    fi
    if [[ -L "$manifest" || ( -e "$manifest" && ! -f "$manifest" ) ]]; then
        echo "Путь manifest должен быть обычным файлом, не ссылкой или каталогом: $manifest" >&2
        return 1
    fi
    if [[ -f "$destination" && -f "$manifest" ]]; then
        local current_size current_revision expected_hash actual_hash magic
        current_size="$(stat -c '%s' "$destination")"
        current_revision="$(sed -n 's/^revision=//p' "$manifest" | head -n 1)"
        expected_hash="$(sed -n 's/^sha256=//p' "$manifest" | head -n 1)"
        magic="$(head -c 4 "$destination" 2>/dev/null || true)"
        if (( current_size >= minimum_bytes )) && [[ "$magic" == "GGUF" \
            && "$current_revision" == "$GIGAAM_REVISION" \
            && "$expected_hash" == "$expected_sha256" \
            && "$expected_hash" =~ ^[[:xdigit:]]{64}$ ]]; then
            actual_hash="$(sha256sum "$destination" | awk '{print $1}')"
            if [[ "$actual_hash" == "$expected_hash" ]]; then
                echo "Модель проверена: $filename ($((current_size / 1000000)) MB, revision $GIGAAM_REVISION)"
                return 0
            fi
        fi
    fi

    echo "Скачиваю $filename (revision $GIGAAM_REVISION)..."
    curl --fail --location --show-error --retry 3 --retry-all-errors \
        --connect-timeout 20 --max-time 1800 --output "$temporary_file" "$model_url"
    local downloaded_size magic downloaded_hash
    downloaded_size="$(stat -c '%s' "$temporary_file")"
    magic="$(head -c 4 "$temporary_file" 2>/dev/null || true)"
    if (( downloaded_size < minimum_bytes )) || [[ "$magic" != "GGUF" ]]; then
        echo "Скачанный файл не похож на GGUF или слишком мал: $filename ($downloaded_size bytes)" >&2
        return 1
    fi
    downloaded_hash="$(sha256sum "$temporary_file" | awk '{print $1}')"
    if [[ "$downloaded_hash" != "$expected_sha256" ]]; then
        echo "SHA256 модели не совпал для $filename: ожидался $expected_sha256, получен $downloaded_hash" >&2
        return 1
    fi
    mv -f -- "$temporary_file" "$destination"
    printf 'revision=%s\nsha256=%s\n' "$GIGAAM_REVISION" "$downloaded_hash" > "$TEMP_DIR/$filename.manifest"
    mv -f -- "$TEMP_DIR/$filename.manifest" "$manifest"
    echo "Готово: $destination ($((downloaded_size / 1000000)) MB; SHA256 сохранён в manifest)"
}

_download_model "gigaam-v3-e2e-rnnt-q8_0.gguf" 200000000 "$expected_q8_sha256"
_download_model "gigaam-v3-e2e-rnnt-q4_k.gguf" 120000000 "$expected_q4_sha256"

if ! version_output="$("$crispasr_bin" --version 2>&1)"; then
    echo "Не удалось запустить CrispASR --version из $crispasr_bin:" >&2
    echo "$version_output" >&2
    exit 1
fi
expected_version="${CRISPASR_VERSION#v}"
if [[ "$version_output" != *"$expected_version"* ]]; then
    echo "Установленная версия не совпадает с запрошенной $CRISPASR_VERSION:" >&2
    echo "$version_output" >&2
    exit 1
fi
printf '%s\n' "$version_output"
printf '%s\n' "$CRISPASR_VERSION" > "$TEMP_DIR/current"
mv -f -- "$TEMP_DIR/current" "$ASR_DIR/runtime/.current"
printf '\nУстановка завершена. CrispASR: %s\n' "$crispasr_bin"
printf '\nВход:  %s\nВыход: %s\n' "$ASR_DIR/data/inbox" "$ASR_DIR/data/outbox"
printf 'Запуск: ./ASR/asr run\nСравнение Q8_0/Q4_K: ./ASR/asr bench --repeats 3 --threads 4\n'

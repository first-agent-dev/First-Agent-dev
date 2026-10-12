from __future__ import annotations

import io
import json
import tempfile
import unittest
import wave
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ASR import transcribe


class TranscribeCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_dir.name)

    def tearDown(self) -> None:
        self.temporary_dir.cleanup()

    def _write_wav(self, path: Path, duration_seconds: int) -> None:
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(bytes(32000 * duration_seconds))

    def _executable(self, path: Path, body: str) -> Path:
        path.write_text(f"#!/usr/bin/env python3\n{body}", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_runner_skips_only_current_results_and_reprocesses_changed_input(self) -> None:
        source = self.root / "meeting.wav"
        self._write_wav(source, 1)
        model = self.root / "gigaam-v3-e2e-rnnt-q8_0.gguf"
        model.write_bytes(b"GGUFfake model")
        output_dir = self.root / "outbox"
        work_dir = self.root / "work"
        count_file = self.root / "inference-count.txt"
        binary = self._executable(
            self.root / "crispasr",
            "import sys\n"
            "from pathlib import Path\n"
            "if '--version' in sys.argv:\n"
            "    print('CrispASR version : 0.8.43')\n"
            "    raise SystemExit(0)\n"
            f"counter = Path({str(count_file)!r})\n"
            "count = int(counter.read_text() or '0') if counter.exists() else 0\n"
            "counter.write_text(str(count + 1))\n"
            "prefix = Path(sys.argv[sys.argv.index('-of') + 1])\n"
            "Path(str(prefix) + '.txt').write_text('Локальная расшифровка', encoding='utf-8')\n",
        )
        args = [
            "asr",
            "--audio",
            str(source),
            "--output-dir",
            str(output_dir),
            "--model",
            str(model),
            "--binary",
            str(binary),
            "--threads",
            "2",
            "--vad",
            "off",
        ]

        def invoke(extra_args: list[str] | None = None) -> tuple[int, str]:
            output = io.StringIO()
            with (
                patch.object(transcribe, "DEFAULT_WORK", work_dir),
                patch("sys.argv", args + (extra_args or [])),
                redirect_stdout(output),
            ):
                return transcribe.main(), output.getvalue()

        exit_code, first_output = invoke()
        self.assertEqual(exit_code, 0)
        self.assertIn("OK meeting.wav", first_output)
        self.assertEqual(count_file.read_text(), "1")
        result_json = output_dir / "meeting.wav.json"
        payload = json.loads(result_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["transcript"], "Локальная расшифровка")

        exit_code, second_output = invoke()
        self.assertEqual(exit_code, 0)
        self.assertIn("SKIP meeting.wav", second_output)
        self.assertEqual(count_file.read_text(), "1")

        self._write_wav(source, 2)
        exit_code, changed_output = invoke()
        self.assertEqual(exit_code, 0)
        self.assertIn("OK meeting.wav", changed_output)
        self.assertEqual(count_file.read_text(), "2")

        exit_code, forced_output = invoke(["--force"])
        self.assertEqual(exit_code, 0)
        self.assertIn("OK meeting.wav", forced_output)
        self.assertEqual(count_file.read_text(), "3")

        alias = self.root / "alias.wav"
        alias.symlink_to(source)
        args[2] = str(alias)
        exit_code, alias_output = invoke()
        self.assertEqual(exit_code, 0)
        self.assertIn("OK alias.wav", alias_output)
        self.assertTrue((output_dir / "alias.wav.md").is_file())
        self.assertEqual(count_file.read_text(), "4")
        exit_code, alias_skip_output = invoke()
        self.assertEqual(exit_code, 0)
        self.assertIn("SKIP alias.wav", alias_skip_output)
        self.assertEqual(count_file.read_text(), "4")


if __name__ == "__main__":
    unittest.main()

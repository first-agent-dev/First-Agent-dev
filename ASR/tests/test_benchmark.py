from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ASR.benchmark import _benchmark_one


class BenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_dir.name)

    def tearDown(self) -> None:
        self.temporary_dir.cleanup()

    def _executable(self, path: Path, body: str) -> Path:
        path.write_text(f"#!/usr/bin/env python3\n{body}", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_benchmark_writes_report_and_reference_scores(self) -> None:
        source = self.root / "sample.wav"
        source.write_bytes(b"fixture")
        q8_model = self.root / "gigaam-v3-e2e-rnnt-q8_0.gguf"
        q4_model = self.root / "gigaam-v3-e2e-rnnt-q4_k.gguf"
        q8_model.write_bytes(b"GGUFq8")
        q4_model.write_bytes(b"GGUFq4")
        reference_dir = self.root / "references"
        reference_dir.mkdir()
        (reference_dir / "sample.txt").write_text("Привет, мир!", encoding="utf-8")

        fake_ffmpeg = self._executable(
            self.root / "ffmpeg",
            "import sys\n"
            "import wave\n"
            "from pathlib import Path\n"
            "with wave.open(str(Path(sys.argv[-1])), 'wb') as audio:\n"
            "    audio.setnchannels(1)\n"
            "    audio.setsampwidth(2)\n"
            "    audio.setframerate(16000)\n"
            "    audio.writeframes(b'\\x00\\x00' * 16000)\n",
        )
        fake_crispasr = self._executable(
            self.root / "crispasr",
            "import sys\n"
            "from pathlib import Path\n"
            "model = Path(sys.argv[sys.argv.index('--model') + 1]).name\n"
            "prefix = Path(sys.argv[sys.argv.index('-of') + 1])\n"
            "text = 'Привет, мир!' if 'q8_0' in model else 'привет мир'\n"
            "Path(str(prefix) + '.txt').write_text(text, encoding='utf-8')\n",
        )
        output_dir = self.root / "reports"
        work_dir = self.root / "work"

        with patch.dict(os.environ, {"FFMPEG_BIN": str(fake_ffmpeg)}):
            markdown_path, json_path = _benchmark_one(
                source,
                models={"q8_0": q8_model, "q4_k": q4_model},
                binary_path=fake_crispasr,
                output_dir=output_dir,
                reference_dir=reference_dir,
                work_dir=work_dir,
                threads=2,
                repeats=2,
                vad_mode="auto",
                vad_threshold=20,
                timeout_seconds=0,
            )

        report = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("WER/CER", markdown_path.read_text(encoding="utf-8"))
        self.assertEqual(report["models"]["q8_0"]["wer"], 0)
        self.assertEqual(report["models"]["q4_k"]["wer"], 0)
        self.assertTrue(report["quantization_comparison"]["normalized_transcripts_identical"])
        self.assertTrue((output_dir / "sample.wav.q8_0.txt").is_file())
        self.assertTrue((output_dir / "sample.wav.q4_k.txt").is_file())


if __name__ == "__main__":
    unittest.main()

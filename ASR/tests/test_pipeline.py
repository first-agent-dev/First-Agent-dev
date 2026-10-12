from __future__ import annotations

import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from ASR.pipeline import (
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
    transcription_outputs_are_current,
    validate_unique_audio_names,
    write_transcription_files,
)


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_dir.name)

    def tearDown(self) -> None:
        self.temporary_dir.cleanup()

    def _executable(self, path: Path, body: str) -> Path:
        path.write_text(f"#!/usr/bin/env python3\n{body}", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_find_audio_files_is_non_recursive_and_filters_hidden_names(self) -> None:
        inbox = self.root / "inbox"
        inbox.mkdir()
        (inbox / "b.wav").touch()
        (inbox / "A.MP3").touch()
        (inbox / "notes.txt").touch()
        (inbox / ".hidden.wav").touch()
        (inbox / "folder").mkdir()
        (inbox / "folder" / "nested.wav").touch()

        self.assertEqual([path.name for path in find_audio_files(inbox)], ["A.MP3", "b.wav"])

    def test_find_audio_files_requires_existing_inbox(self) -> None:
        with self.assertRaises(PipelineError):
            find_audio_files(self.root / "missing")

    def test_model_resolution_rejects_non_gguf_files(self) -> None:
        invalid_model = self.root / "not-a-model.gguf"
        invalid_model.write_bytes(b"HTML error page")

        with self.assertRaisesRegex(PipelineError, "сигнатуры GGUF"):
            resolve_model(invalid_model)

    def test_vad_auto_threshold_and_explicit_modes(self) -> None:
        self.assertFalse(choose_vad("auto", 20.0))
        self.assertTrue(choose_vad("auto", 20.01))
        self.assertTrue(choose_vad("on", 1.0))
        self.assertFalse(choose_vad("off", 120.0))
        with self.assertRaises(PipelineError):
            choose_vad("sometimes", 30.0)

    def test_prepare_audio_reuses_compatible_wav_without_ffmpeg(self) -> None:
        source = self.root / "ready.wav"
        with wave.open(str(source), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(bytes(16000))

        result = prepare_audio(source, self.root / "unused" / "normalized.wav", ffmpeg_binary="/missing/ffmpeg")

        self.assertEqual(result.path, source.resolve())
        self.assertAlmostEqual(result.duration_seconds, 0.5)
        self.assertEqual(result.preparation_seconds, 0.0)

    def test_prepare_audio_normalizes_to_mono_16khz_wav(self) -> None:
        source = self.root / "source.mp3"
        source.write_bytes(b"input fixture")
        fake_ffmpeg = self._executable(
            self.root / "ffmpeg",
            "import sys\n"
            "import wave\n"
            "from pathlib import Path\n"
            "output = Path(sys.argv[-1])\n"
            "with wave.open(str(output), 'wb') as audio:\n"
            "    audio.setnchannels(1)\n"
            "    audio.setsampwidth(2)\n"
            "    audio.setframerate(16000)\n"
            "    audio.writeframes(b'\\x00\\x00' * 16000)\n",
        )

        result = prepare_audio(source, self.root / "work" / "normalized.wav", ffmpeg_binary=fake_ffmpeg)

        self.assertAlmostEqual(result.duration_seconds, 1.0)
        self.assertEqual(result.path.suffix, ".wav")
        with wave.open(str(result.path), "rb") as audio:
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getframerate(), 16000)
            self.assertEqual(audio.getsampwidth(), 2)

    def test_run_inference_reads_utf8_text_output(self) -> None:
        audio = self.root / "prepared.wav"
        audio.touch()
        model = self.root / "gigaam-v3-e2e-rnnt-q8_0.gguf"
        model.write_bytes(b"GGUFtest model")
        fake_binary = self._executable(
            self.root / "crispasr",
            "import sys\n"
            "from pathlib import Path\n"
            "prefix = Path(sys.argv[sys.argv.index('-of') + 1])\n"
            "Path(str(prefix) + '.txt').write_text('Привет, мир!\\n', encoding='utf-8')\n",
        )

        result = run_inference(
            audio,
            model,
            self.root / "result",
            threads=4,
            vad_enabled=True,
            binary_path=fake_binary,
        )

        self.assertEqual(result.transcript, "Привет, мир!")
        self.assertGreaterEqual(result.inference_seconds, 0)

    def test_prepare_audio_rejects_output_that_violates_model_contract(self) -> None:
        source = self.root / "source.mp3"
        source.write_bytes(b"fixture")
        fake_ffmpeg = self._executable(
            self.root / "ffmpeg-stereo",
            "import sys\n"
            "import wave\n"
            "from pathlib import Path\n"
            "with wave.open(str(Path(sys.argv[-1])), 'wb') as audio:\n"
            "    audio.setnchannels(2)\n"
            "    audio.setsampwidth(2)\n"
            "    audio.setframerate(16000)\n"
            "    audio.writeframes(bytes(32000))\n",
        )

        with self.assertRaisesRegex(PipelineError, "контракту GigaAM"):
            prepare_audio(source, self.root / "work" / "normalized.wav", ffmpeg_binary=fake_ffmpeg)

    def test_unique_names_reject_case_collisions_and_control_characters(self) -> None:
        with self.assertRaisesRegex(PipelineError, "конфликтуют"):
            validate_unique_audio_names([Path("/left/Meeting.wav"), Path("/right/meeting.WAV")])
        with self.assertRaisesRegex(PipelineError, "управляющий символ"):
            validate_unique_audio_names([Path("bad\nname.wav")])

    def test_run_lock_rejects_an_overlapping_job(self) -> None:
        lock_path = self.root / "work" / ".asr.lock"
        with exclusive_run_lock(lock_path):
            with self.assertRaisesRegex(PipelineError, "уже выполняется"):
                with exclusive_run_lock(lock_path):
                    self.fail("nested lock should be rejected")

    def test_resolver_honors_installer_selected_runtime_version(self) -> None:
        runtime_dir = self.root / "runtime" / "v0.8.46" / "bin"
        runtime_dir.mkdir(parents=True)
        binary = self._executable(runtime_dir / "crispasr", "pass\n")
        (self.root / "runtime" / ".current").write_text("v0.8.46\n", encoding="ascii")

        with patch("ASR.pipeline.ASR_DIR", self.root):
            self.assertEqual(resolve_crispasr_binary(), binary.resolve())

    def test_runtime_version_is_read_from_selected_executable(self) -> None:
        binary = self._executable(
            self.root / "crispasr-version",
            "import sys\nprint('CrispASR version : 0.8.46', file=sys.stderr)\n",
        )
        self.assertEqual(crispasr_version(binary), "0.8.46")

    def test_writer_outputs_markdown_and_machine_readable_json(self) -> None:
        source = self.root / "meeting.wav"
        source.write_bytes(b"audio")
        model = self.root / "gigaam-v3-e2e-rnnt-q8_0.gguf"
        model.write_bytes(b"GGUFmodel")
        binary = self._executable(self.root / "crispasr", "pass\n")
        result = Transcription(
            source=source,
            model=model,
            transcript="Привет, мир!",
            audio_seconds=12.0,
            preparation_seconds=0.5,
            inference_seconds=6.0,
            threads=4,
            vad_enabled=False,
            runtime_version="0.8.43",
            runtime_binary=binary,
            vad_mode="off",
        )

        markdown_path, json_path = write_transcription_files(result, self.root / "outbox")
        payload = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("## Текст", markdown_path.read_text(encoding="utf-8"))
        self.assertIn("Привет, мир!", markdown_path.read_text(encoding="utf-8"))
        self.assertIn("GigaAM-v3, Q8_0", markdown_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["quantization"], "Q8_0")
        self.assertEqual(payload["device"], "cpu")
        self.assertEqual(payload["runtime"], "CrispASR 0.8.43")
        self.assertEqual(payload["real_time_factor"], 0.5)
        self.assertEqual(payload["times_real_time"], 2.0)
        self.assertEqual(payload["vad_mode"], "off")
        self.assertTrue(
            transcription_outputs_are_current(
                source,
                model,
                binary,
                markdown_path.parent,
                threads=4,
                vad_mode="off",
                vad_threshold_seconds=20.0,
            )
        )
        self.assertFalse(
            transcription_outputs_are_current(
                source,
                model,
                binary,
                markdown_path.parent,
                threads=8,
                vad_mode="off",
                vad_threshold_seconds=20.0,
            )
        )
        markdown_path.write_text("manual edit", encoding="utf-8")
        self.assertFalse(
            transcription_outputs_are_current(
                source,
                model,
                binary,
                markdown_path.parent,
                threads=4,
                vad_mode="off",
                vad_threshold_seconds=20.0,
            )
        )


if __name__ == "__main__":
    unittest.main()

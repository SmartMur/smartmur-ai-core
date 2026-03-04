"""Tests for voice transcription module."""

from __future__ import annotations

from unittest.mock import patch

from superpowers.voice_transcriber import transcribe


def test_missing_audio_file():
    result = transcribe("/nonexistent/file.ogg")
    assert "[error: audio file not found" in result


def test_missing_model(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"fake audio")
    result = transcribe(audio, model_path="/nonexistent/model.bin")
    assert "[error: whisper model not found" in result


def test_missing_whisper_cli(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"fake audio")
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake model")
    with patch(
        "shutil.which", side_effect=lambda x: None if x == "whisper-cli" else "/usr/bin/ffmpeg"
    ):
        result = transcribe(audio, model_path=model)
    assert "[error: whisper-cli not found" in result


def test_missing_ffmpeg(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"fake audio")
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake model")
    with patch(
        "shutil.which",
        side_effect=lambda x: "/usr/local/bin/whisper-cli" if x == "whisper-cli" else None,
    ):
        result = transcribe(audio, model_path=model)
    assert "[error: ffmpeg not found" in result


def test_successful_transcribe(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"fake audio")
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake model")

    with (
        patch("shutil.which", return_value="/usr/local/bin/fake"),
        patch("subprocess.run") as mock_run,
    ):
        # ffmpeg succeeds
        mock_run.side_effect = [
            type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            type("R", (), {"returncode": 0, "stdout": "Hello world", "stderr": ""})(),
        ]
        result = transcribe(audio, model_path=model)
    assert result == "Hello world"


def test_ffmpeg_failure(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"fake audio")
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake model")

    with (
        patch("shutil.which", return_value="/usr/local/bin/fake"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = type(
            "R", (), {"returncode": 1, "stdout": "", "stderr": "bad format"}
        )()
        result = transcribe(audio, model_path=model)
    assert "[error: ffmpeg conversion failed" in result


def test_download_telegram_voice_success(tmp_path):
    import json

    from superpowers.voice_transcriber import download_telegram_voice

    get_file_resp = json.dumps({"ok": True, "result": {"file_path": "voice/file_0.oga"}}).encode()

    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.read.return_value = get_file_resp
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        patch("urllib.request.urlretrieve"),
    ):
        result = download_telegram_voice("fake-token", "fake-file-id")

    assert result is not None
    assert str(result).endswith("voice.ogg")

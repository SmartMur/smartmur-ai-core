"""Offline voice transcription using whisper.cpp — no API key needed."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MODEL = Path.home() / ".claude-superpowers" / "models" / "ggml-base.en.bin"


def transcribe(audio_path: str | Path, model_path: str | Path | None = None) -> str:
    """Transcribe an audio file using whisper-cli.

    Accepts any format ffmpeg can read (ogg, mp3, m4a, wav, etc.).
    Returns the transcribed text, or an error message.
    """
    audio_path = Path(audio_path)
    model_path = Path(model_path) if model_path else DEFAULT_MODEL

    if not audio_path.is_file():
        return f"[error: audio file not found: {audio_path}]"
    if not model_path.is_file():
        return "[error: whisper model not found — run: curl -L -o ~/.claude-superpowers/models/ggml-base.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin]"
    if not shutil.which("whisper-cli"):
        return "[error: whisper-cli not found — run: brew install whisper-cpp]"

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"

        # Convert to 16kHz mono WAV (whisper requirement)
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return "[error: ffmpeg not found — run: brew install ffmpeg]"

        result = subprocess.run(
            [ffmpeg, "-i", str(audio_path), "-ar", "16000", "-ac", "1",
             "-c:a", "pcm_s16le", str(wav_path), "-y"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return f"[error: ffmpeg conversion failed: {result.stderr[:200]}]"

        # Transcribe
        result = subprocess.run(
            ["whisper-cli", "-m", str(model_path), "-f", str(wav_path),
             "--no-timestamps", "-np"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return f"[error: whisper failed: {result.stderr[:200]}]"

        # Extract text — whisper outputs to stdout
        text = result.stdout.strip()
        if not text:
            return "[no speech detected]"
        return text


def download_telegram_voice(bot_token: str, file_id: str) -> Path | None:
    """Download a Telegram voice message and return the local path."""
    import json
    import urllib.request

    try:
        # Get file path from Telegram
        url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())

        if not data.get("ok"):
            return None

        file_path = data["result"]["file_path"]
        dl_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

        # Download to temp file
        tmp = Path(tempfile.mkdtemp()) / "voice.ogg"
        urllib.request.urlretrieve(dl_url, str(tmp))
        return tmp
    except Exception as exc:
        logger.error("Failed to download voice: %s", exc)
        return None

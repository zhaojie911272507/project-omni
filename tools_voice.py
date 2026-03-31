"""Voice tools for Project Omni.

TTS (Text-to-Speech) and ASR (Automatic Speech Recognition).
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agent import tool


# ─────────────────────────────────────────────────────────────────────────────
# TTS (Text-to-Speech)
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="text_to_speech",
    description=(
        "Convert text to speech using edge-tts. "
        "Returns base64-encoded audio that can be played or saved to a file."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice": {
                "type": "string",
                "description": "Voice name. Default: zh-CN-XiaoxiaoNeural",
            },
            "output_file": {
                "type": "string",
                "description": "Save to file instead of returning base64",
            },
        },
        "required": ["text"],
    },
)
def text_to_speech(
    text: str,
    voice: str | None = None,
    output_file: str | None = None,
) -> str:
    """Convert text to speech."""
    try:
        import edge_tts
    except ImportError:
        return "[error] edge-tts not installed. Run: pip install edge-tts"

    if not text.strip():
        return "[error] Empty text"

    # Default voice
    voice = voice or os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")

    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        return audio_data

    # Run async
    import asyncio

    audio_data = asyncio.run(_generate())

    if not audio_data:
        return "[error] No audio generated"

    # Save to file or return base64
    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "wb") as f:
            f.write(audio_data)
        return f"[saved {len(audio_data)} bytes to {output_file}]"

    # Return base64
    b64 = base64.b64encode(audio_data).decode()
    return f"[audio base64, {len(b64)} chars]"


@tool(
    name="list_tts_voices",
    description="List available edge-tts voices.",
    parameters={
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "description": "Filter by language code (e.g., 'zh-CN', 'en-US')",
            },
        },
    },
)
def list_tts_voices(language: str | None = None) -> str:
    """List available TTS voices."""
    try:
        import edge_tts
    except ImportError:
        return "[error] edge-tts not installed. Run: pip install edge-tts"

    async def _list():
        voices = await edge_tts.list_voices()
        return voices

    voices = asyncio.run(_list())

    # Filter by language if specified
    if language:
        voices = [v for v in voices if v["Language"] == language]

    # Format output
    output = f"Available voices (showing {len(voices)}):\n\n"
    shown = set()
    for v in voices[:50]:  # Limit output
        name = v["ShortName"]
        if name in shown:
            continue
        shown.add(name)
        output += f"- {name} ({v['Gender']}, {v['Language']})\n"
        if v.get("FriendlyName"):
            output += f"  {v['FriendlyName']}\n"

    return output


# ─────────────────────────────────────────────────────────────────────────────
# ASR (Speech-to-Text)
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="speech_to_text",
    description=(
        "Convert speech (audio file) to text using Whisper. "
        "Supports mp3, wav, m4a, flac, ogg formats."
    ),
    parameters={
        "type": "object",
        "properties": {
            "audio_path": {"type": "string", "description": "Path to audio file"},
            "language": {
                "type": "string",
                "description": "Language code (e.g., 'zh', 'en'). Auto-detect if not specified",
            },
            "model": {
                "type": "string",
                "description": "Whisper model: 'tiny', 'base', 'small', 'medium', 'large'. Default: base",
            },
        },
        "required": ["audio_path"],
    },
)
def speech_to_text(
    audio_path: str,
    language: str | None = None,
    model: str = "base",
) -> str:
    """Convert speech to text."""
    if not os.path.exists(audio_path):
        return f"[error] File not found: {audio_path}"

    try:
        import whisper
    except ImportError:
        return "[error] whisper not installed. Run: pip install openai-whisper"

    try:
        # Load model
        result = whisper.load_model(model)

        # Transcribe
        options = {"task": "transcribe"}
        if language:
            options["language"] = language

        result = result.transcribe(audio_path, **options)

        text = result.get("text", "").strip()
        if not text:
            return "[warning] No speech detected"

        # Get additional info
        info = f"[language: {result.get('language', 'unknown')}, "
        info += f"duration: {result.get('duration', 0):.1f}s]\n\n{text}"

        return info

    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


@tool(
    name="transcribe_youtube",
    description=(
        "Download and transcribe audio from YouTube videos. "
        "Uses yt-dlp to download and Whisper to transcribe."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "YouTube video URL"},
            "language": {
                "type": "string",
                "description": "Language code for transcription",
            },
        },
        "required": ["url"],
    },
)
def transcribe_youtube(url: str, language: str | None = None) -> str:
    """Transcribe YouTube video."""
    try:
        import yt_dlp
        import whisper
    except ImportError:
        return "[error] yt-dlp and whisper required. Run: pip install yt-dlp openai-whisper"

    try:
        # Download audio
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "/tmp/yt_audio.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                }
            ],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Transcribe
        audio_path = "/tmp/yt_audio.wav"
        if not os.path.exists(audio_path):
            return "[error] Failed to download audio"

        model = whisper.load_model("base")
        options = {"task": "transcribe"}
        if language:
            options["language"] = language

        result = model.transcribe(audio_path, **options)

        # Cleanup
        os.remove(audio_path)

        text = result.get("text", "").strip()
        if not text:
            return "[warning] No speech detected"

        return f"[transcribed]\n\n{text}"

    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


# Helper to run async code
import asyncio
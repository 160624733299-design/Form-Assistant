"""Language support exposed by Sarvam Bulbul v3, separate from STT support."""

from typing import Final

TTS_LANGUAGES: Final[dict[str, str]] = {
    "bn-IN": "Bengali",
    "en-IN": "English",
    "gu-IN": "Gujarati",
    "hi-IN": "Hindi",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "mr-IN": "Marathi",
    "od-IN": "Odia",
    "pa-IN": "Punjabi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
}

TTS_AUDIO_CONTENT_TYPES: Final[dict[str, str]] = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "aac": "audio/aac",
    "opus": "audio/ogg; codecs=opus",
    "flac": "audio/flac",
    "linear16": "audio/L16",
    "mulaw": "audio/basic",
    "alaw": "audio/basic",
}

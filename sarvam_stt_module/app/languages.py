"""Sarvam Saaras language configuration.

Keep this map as the sole place to add or change UI language options.
"""

from typing import Final

LANGUAGES: Final[dict[str, str]] = {
    "hi-IN": "Hindi",
    "bn-IN": "Bengali",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "mr-IN": "Marathi",
    "od-IN": "Odia",
    "pa-IN": "Punjabi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "en-IN": "English",
    "gu-IN": "Gujarati",
    "as-IN": "Assamese",
    "ur-IN": "Urdu",
    "ne-IN": "Nepali",
    "kok-IN": "Konkani",
    "ks-IN": "Kashmiri",
    "sd-IN": "Sindhi",
    "sa-IN": "Sanskrit",
    "sat-IN": "Santali",
    "mni-IN": "Manipuri",
    "brx-IN": "Bodo",
    "mai-IN": "Maithili",
    "doi-IN": "Dogri",
}

AUTO_DETECT: Final[str] = "unknown"
SUPPORTED_LANGUAGE_CODES: Final[frozenset[str]] = frozenset({AUTO_DETECT, *LANGUAGES})

# Browsers normally record audio/webm; every MIME type below maps to a format
# accepted by Sarvam's REST STT API. The filename extension is checked too.
SUPPORTED_CONTENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave",
        "audio/aac", "audio/x-aac", "audio/aiff", "audio/x-aiff", "audio/ogg",
        "audio/opus", "audio/flac", "audio/x-flac", "audio/mp4", "audio/x-m4a",
        "audio/amr", "audio/x-ms-wma", "audio/webm", "video/webm",
        "audio/pcm", "audio/l16",
    }
)
SUPPORTED_FILE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".mp3", ".wav", ".aac", ".aiff", ".aif", ".ogg", ".opus", ".flac", ".mp4", ".m4a", ".amr", ".wma", ".webm", ".pcm"}
)

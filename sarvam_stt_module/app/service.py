from typing import Any

import httpx
from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

from .config import Settings


class SarvamTranscriptionError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SarvamSTTService:
    """Small adapter that keeps the Sarvam SDK outside the API route."""

    def __init__(self, settings: Settings, client: SarvamAI | Any | None = None) -> None:
        if settings.sarvam_stt_model not in {"saaras:v3", "saaras:v4"}:
            raise ValueError("SARVAM_STT_MODEL must be 'saaras:v3' or 'saaras:v4'.")
        self.settings = settings
        self.client = client

    def _client(self) -> SarvamAI | Any:
        if not self.settings.sarvam_api_key:
            raise SarvamTranscriptionError(
                "Sarvam is not configured. Set SARVAM_API_KEY on the backend.", 500
            )
        return self.client or SarvamAI(api_subscription_key=self.settings.sarvam_api_key)

    def transcribe(
        self,
        *,
        audio: bytes,
        filename: str,
        content_type: str | None,
        language_code: str,
        input_audio_codec: str | None = None,
    ) -> tuple[str, str | None]:
        try:
            request = {
                "file": (filename, audio, content_type or "application/octet-stream"),
                "model": self.settings.sarvam_stt_model,
                "mode": "transcribe",
                "language_code": language_code,
            }
            if input_audio_codec:
                request["input_audio_codec"] = input_audio_codec
            response = self._client().speech_to_text.transcribe(**request)
        except SarvamTranscriptionError:
            raise
        except (ApiError, httpx.HTTPError) as error:
            status_code = getattr(error, "status_code", 502)
            if status_code in {400, 422}:
                message, public_status = "Sarvam could not process this audio file.", 422
            elif status_code == 429:
                message, public_status = "Sarvam rate limit reached. Please try again shortly.", 503
            elif status_code == 403:
                message, public_status = "Sarvam authentication failed. Contact the backend administrator.", 502
            else:
                message, public_status = "Speech recognition service is temporarily unavailable.", 502
            raise SarvamTranscriptionError(message, public_status) from error

        transcript = getattr(response, "transcript", None)
        if not isinstance(transcript, str):
            raise SarvamTranscriptionError("Sarvam returned an invalid transcription response.", 502)
        return transcript, getattr(response, "language_code", None)

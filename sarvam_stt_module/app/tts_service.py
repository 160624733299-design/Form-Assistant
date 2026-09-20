from typing import Any

import httpx
from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

from .config import Settings
from .tts_languages import TTS_AUDIO_CONTENT_TYPES, TTS_LANGUAGES


class SarvamTextToSpeechError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SarvamTTSService:
    """Adapter around Sarvam Bulbul v3 REST text-to-speech."""

    def __init__(self, settings: Settings, client: SarvamAI | Any | None = None) -> None:
        if settings.sarvam_tts_model != "bulbul:v3":
            raise ValueError("SARVAM_TTS_MODEL must be 'bulbul:v3'.")
        if settings.sarvam_tts_output_audio_codec not in TTS_AUDIO_CONTENT_TYPES:
            raise ValueError("SARVAM_TTS_OUTPUT_AUDIO_CODEC is not supported by Bulbul v3.")
        self.settings = settings
        self.client = client

    def _client(self) -> SarvamAI | Any:
        if not self.settings.sarvam_api_key:
            raise SarvamTextToSpeechError(
                "Sarvam is not configured. Set SARVAM_API_KEY on the backend.", 500
            )
        return self.client or SarvamAI(api_subscription_key=self.settings.sarvam_api_key)

    def synthesize(self, *, text: str, language_code: str) -> tuple[str, str]:
        if language_code not in TTS_LANGUAGES:
            raise SarvamTextToSpeechError(
                f"Spoken output is currently unavailable for language '{language_code}'.", 422
            )
        if not text.strip():
            raise SarvamTextToSpeechError("The answer-generation service returned empty response text.", 502)
        if len(text) > 2500:
            raise SarvamTextToSpeechError(
                "Response text exceeds Bulbul v3's 2500-character REST limit.", 422
            )

        try:
            response = self._client().text_to_speech.convert(
                text=text,
                language_code=language_code,
                speaker=self.settings.sarvam_tts_speaker,
                model=self.settings.sarvam_tts_model,
                output_audio_codec=self.settings.sarvam_tts_output_audio_codec,
            )
        except SarvamTextToSpeechError:
            raise
        except (ApiError, httpx.HTTPError) as error:
            status_code = getattr(error, "status_code", 502)
            if status_code in {400, 422}:
                message, public_status = "Sarvam could not synthesize this response text.", 422
            elif status_code == 429:
                message, public_status = "Sarvam rate limit reached. Please try again shortly.", 503
            elif status_code == 403:
                message, public_status = "Sarvam authentication failed. Contact the backend administrator.", 502
            else:
                message, public_status = "Speech synthesis service is temporarily unavailable.", 502
            raise SarvamTextToSpeechError(message, public_status) from error

        audios = getattr(response, "audios", None)
        if not isinstance(audios, list) or not audios or not isinstance(audios[0], str):
            raise SarvamTextToSpeechError("Sarvam returned an invalid speech-synthesis response.", 502)
        return audios[0], TTS_AUDIO_CONTENT_TYPES[self.settings.sarvam_tts_output_audio_codec]

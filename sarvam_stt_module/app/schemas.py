from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    transcript: str = Field(description="Speech transcribed by Sarvam.")
    language_code: str | None = Field(
        description="Detected or selected BCP-47 language code; null when not detected."
    )


class VoiceResponse(TranscriptionResponse):
    response_text: str = Field(description="Answer text returned by the main application's AnswerService.")
    response_audio: str = Field(description="Base64-encoded Bulbul v3 audio.")
    audio_content_type: str = Field(description="MIME type for response_audio after base64 decoding.")

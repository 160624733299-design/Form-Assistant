from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool


from .config import Settings, get_settings
from .languages import (
    SUPPORTED_CONTENT_TYPES,
    SUPPORTED_FILE_EXTENSIONS,
    SUPPORTED_LANGUAGE_CODES,
)
from .schemas import TranscriptionResponse
from .service import SarvamSTTService, SarvamTranscriptionError


app = FastAPI(title="Sarvam Speech-to-Text Module", version="1.0.0")


def get_stt_service(settings: Annotated[Settings, Depends(get_settings)]) -> SarvamSTTService:
    return SarvamSTTService(settings)






def _validate_upload(upload: UploadFile, audio: bytes, settings: Settings) -> None:
    filename = upload.filename or "audio"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content_type = (upload.content_type or "").lower()

    if not audio:
        raise HTTPException(status_code=400, detail="Audio file is empty.")

    if len(audio) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio upload exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB module limit.",
        )

    if extension not in SUPPORTED_FILE_EXTENSIONS and content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported audio format. Use WAV, MP3, AAC, AIFF, OGG/Opus, "
                "FLAC, MP4/M4A, AMR, WMA, WebM, or PCM."
            ),
        )


def _is_pcm_upload(upload: UploadFile) -> bool:
    filename = upload.filename or ""

    return filename.lower().endswith(".pcm") or (
        upload.content_type or ""
    ).lower() in {
        "audio/pcm",
        "audio/l16",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
    language_code: Annotated[str, Form()] = "unknown",
    duration_seconds: Annotated[float | None, Form()] = None,
    input_audio_codec: Annotated[str | None, Form()] = None,
    settings: Settings = Depends(get_settings),
    service: SarvamSTTService = Depends(get_stt_service),
) -> TranscriptionResponse:
    """Return only Sarvam's transcript; this route performs no AI/chat processing."""

    # Swagger may send 0 when the optional duration field is left empty.
    # Treat 0 as "not provided".
    if duration_seconds == 0:
        duration_seconds = None

    if language_code not in SUPPORTED_LANGUAGE_CODES:
        raise HTTPException(
            status_code=422,
            detail="Unsupported language_code. Use 'unknown' or a supported Sarvam BCP-47 code.",
        )

    if duration_seconds is not None:
        if duration_seconds < 0 or duration_seconds > settings.max_audio_duration_seconds:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"REST transcription accepts audio up to "
                    f"{settings.max_audio_duration_seconds:g} seconds."
                ),
            )

    if input_audio_codec is not None and input_audio_codec not in {
        "pcm_s16le",
        "pcm_l16",
        "pcm_raw",
    }:
        raise HTTPException(
            status_code=422,
            detail="input_audio_codec must be pcm_s16le, pcm_l16, or pcm_raw.",
        )

    if _is_pcm_upload(file) and not input_audio_codec:
        raise HTTPException(
            status_code=422,
            detail=(
                "PCM uploads require input_audio_codec "
                "(pcm_s16le, pcm_l16, or pcm_raw) at 16 kHz."
            ),
        )

    audio = await file.read()

    _validate_upload(file, audio, settings)

    try:
        transcript, detected_language = await run_in_threadpool(
            service.transcribe,
            audio=audio,
            filename=file.filename or "audio.webm",
            content_type=file.content_type,
            language_code=language_code,
            input_audio_codec=input_audio_codec,
        )

    except SarvamTranscriptionError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.message,
        ) from error

    finally:
        await file.close()

    return TranscriptionResponse(
        transcript=transcript,
        language_code=detected_language,
    )



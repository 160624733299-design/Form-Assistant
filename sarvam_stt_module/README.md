# Sarvam Voice module (STT + application answer boundary + TTS)

An isolated FastAPI module for Member 2's scope only:

`microphone audio -> STT -> main application answer service -> TTS -> text + audio`

It does not implement an LLM, database, authentication system, chatbot, or business-answer logic.

## Setup

Use Python 3.11+ and the module directory:

```powershell
cd sarvam_stt_module
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

In `.env`, set the backend-only value:

```env
SARVAM_API_KEY=your_real_key
```

Optional backend settings are documented in `.env.example`:

```env
SARVAM_STT_MODEL=saaras:v3
SARVAM_TTS_MODEL=bulbul:v3
SARVAM_TTS_SPEAKER=shubh
SARVAM_TTS_OUTPUT_AUDIO_CODEC=mp3
```

Never commit `.env`, and never use `SARVAM_API_KEY` or the Sarvam SDK in React/browser code.

## Run

```powershell
cd sarvam_stt_module
python -m uvicorn app.main:app --reload --port 8000
```

Check `GET http://127.0.0.1:8000/health`, or use the FastAPI documentation at `http://127.0.0.1:8000/docs`.

## API

`POST /transcribe` accepts `multipart/form-data`.

| Field | Required | Description |
| --- | --- | --- |
| `file` | Yes | Audio file. Sarvam REST supports WAV, MP3, AAC, AIFF, OGG/Opus, FLAC, MP4/M4A, AMR, WMA, WebM, and PCM. |
| `language_code` | No | Sarvam BCP-47 code, or `unknown` for automatic detection. Default: `unknown`. |
| `duration_seconds` | No, recommended | Browser-measured recording duration. The route rejects a supplied value greater than 30 seconds. |
| `input_audio_codec` | PCM only | `pcm_s16le`, `pcm_l16`, or `pcm_raw`; PCM must be 16 kHz. |

Sarvam's synchronous REST STT API permits audio up to 30 seconds. Frontends should stop `MediaRecorder` at or before that limit. The optional duration field provides an early, clear application-level validation; Sarvam remains the final authority for actual uploaded audio duration.

Initial test selections:

| Language | `language_code` |
| --- | --- |
| English | `en-IN` |
| Hindi | `hi-IN` |
| Telugu | `te-IN` |
| Automatic detection | `unknown` |

All current Sarvam Saaras language codes are present in `app/languages.py`, so teammates can expose more language choices without changing the route or SDK integration.

Example with curl:

```powershell
curl.exe -X POST http://127.0.0.1:8000/transcribe `
  -F "file=@sample.webm;type=audio/webm" `
  -F "language_code=te-IN" `
  -F "duration_seconds=4.2"
```

Response:

```json
{
  "transcript": "నమస్తే ప్రపంచం",
  "language_code": "te-IN"
}
```

The route uses the official `sarvamai` Python SDK (`SarvamAI(...).speech_to_text.transcribe`) and sends `model=saaras:v3`, `mode=transcribe`. `saaras:v3` is Sarvam's currently documented recommended/default STT model. The model is configurable through `SARVAM_STT_MODEL` and is restricted to the versions supported by installed SDK 0.1.34 (`saaras:v3` and `saaras:v4`).

## Teammate integration

From React, record using the built-in `MediaRecorder`, construct `FormData`, append the audio under exactly `file`, append a selected `language_code`, then post it to the existing backend's mounted `/transcribe` route. Consume only `transcript` and `language_code` from the response. Keep any later AI/chat handling in the owning team's separate flow.

When incorporating this into an existing FastAPI server, prefer importing and mounting this route/module rather than starting a second server. Configure CORS only in the team's existing application entry point with the team's frontend origins.

## Voice API: audio-only input

`POST /voice` accepts exactly one user-facing field: `file`, the user's audio. It does not accept typed text, `response_text`, a query, or a language field. It always asks Saaras STT to auto-detect the language.

The flow is:

`file -> STT -> transcript + detected language -> AnswerService -> response_text -> Bulbul v3 -> response_audio`

The response is:

```json
{
  "transcript": "...",
  "language_code": "hi-IN",
  "response_text": "...",
  "response_audio": "<base64 MP3 audio>",
  "audio_content_type": "audio/mpeg"
}
```

`response_audio` is base64 because that is Sarvam REST's response format. Decode and play it in React without sending any API key to the browser:

```js
const bytes = Uint8Array.from(atob(result.response_audio), char => char.charCodeAt(0));
const url = URL.createObjectURL(new Blob([bytes], { type: result.audio_content_type }));
new Audio(url).play();
```

Bulbul v3 supports Bengali, English, Gujarati, Hindi, Kannada, Malayalam, Marathi, Odia, Punjabi, Tamil, and Telugu. The separate `app/tts_languages.py` map enforces this. If STT detects another Saaras language, `/voice` returns a clear `422` rather than silently switching languages.

### Connecting the main application answer logic

`app/answer_service.py` intentionally has no answer-generation implementation. Its default safe implementation returns `503` until the main application supplies an `AnswerService`. The owning team should replace this dependency with an adapter that implements:

```python
def generate_response(transcript: str, language_code: str) -> str:
    # Call the main application's existing answer logic here.
    # Return answer text in language_code.
```

The user still submits only audio to `/voice`; answer text never becomes a request field. The unit tests override this dependency with a mock, together with mocked Sarvam STT and TTS services, to prove the complete audio -> transcript -> answer boundary -> text -> audio flow without an external AI provider or a real Sarvam key.

To test a real mounted application with audio only:

```powershell
curl.exe -X POST http://127.0.0.1:8000/voice `
  -F "file=@sample.webm;type=audio/webm"
```

Until the main app registers its answer-service adapter, the real endpoint correctly returns `503` instead of inventing an answer.

## Tests

The tests mock Sarvam responses and never need an API key or network connection:

```powershell
cd sarvam_stt_module
python -m unittest discover -s tests -v
```

They cover successful WebM upload, automatic detection, validation failures, duration enforcement, empty audio, SDK-response mapping, missing backend configuration, Bulbul v3 base64 audio, safe Sarvam API failures, and the mocked audio-only `/voice` end-to-end flow for English, Hindi, and Telugu.

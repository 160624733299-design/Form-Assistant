import unittest

from fastapi.testclient import TestClient
from sarvamai.core.api_error import ApiError

from app.config import Settings, get_settings
from app.main import app, get_stt_service
from app.service import SarvamSTTService, SarvamTranscriptionError
from app.tts_service import SarvamTTSService, SarvamTextToSpeechError


class FakeSarvamService:
    def __init__(self) -> None:
        self.calls = []

    def transcribe(self, **kwargs):
        self.calls.append(kwargs)
        return "నమస్తే ప్రపంచం", "te-IN"


class TranscribeRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_service = FakeSarvamService()
        app.dependency_overrides[get_settings] = lambda: Settings(sarvam_api_key="test-key")
        app.dependency_overrides[get_stt_service] = lambda: self.fake_service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_transcribes_telugu_webm(self) -> None:
        response = self.client.post(
            "/transcribe",
            files={"file": ("speech.webm", b"mock-audio", "audio/webm")},
            data={"language_code": "te-IN", "duration_seconds": "3.5"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"transcript": "నమస్తే ప్రపంచం", "language_code": "te-IN"})
        self.assertEqual(self.fake_service.calls[0]["language_code"], "te-IN")

    def test_initial_language_choices_are_accepted(self) -> None:
        for language_code in ("en-IN", "hi-IN", "te-IN"):
            with self.subTest(language_code=language_code):
                response = self.client.post(
                    "/transcribe",
                    files={"file": ("speech.wav", b"mock-audio", "audio/wav")},
                    data={"language_code": language_code, "duration_seconds": "2"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.fake_service.calls[-1]["language_code"], language_code)

    def test_accepts_auto_detection(self) -> None:
        response = self.client.post(
            "/transcribe",
            files={"file": ("speech.wav", b"mock-audio", "audio/wav")},
            data={"language_code": "unknown", "duration_seconds": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake_service.calls[0]["language_code"], "unknown")

    def test_rejects_unsupported_language(self) -> None:
        response = self.client.post(
            "/transcribe",
            files={"file": ("speech.wav", b"mock-audio", "audio/wav")},
            data={"language_code": "fr-FR"},
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_duration_over_limit(self) -> None:
        response = self.client.post(
            "/transcribe",
            files={"file": ("speech.wav", b"mock-audio", "audio/wav")},
            data={"language_code": "en-IN", "duration_seconds": "30.1"},
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_pcm_without_codec(self) -> None:
        response = self.client.post(
            "/transcribe",
            files={"file": ("speech.pcm", b"mock-audio", "audio/pcm")},
            data={"language_code": "hi-IN", "duration_seconds": "2"},
        )
        self.assertEqual(response.status_code, 422)

    def test_forwards_pcm_codec(self) -> None:
        response = self.client.post(
            "/transcribe",
            files={"file": ("speech.pcm", b"mock-audio", "audio/pcm")},
            data={
                "language_code": "hi-IN",
                "duration_seconds": "2",
                "input_audio_codec": "pcm_s16le",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake_service.calls[-1]["input_audio_codec"], "pcm_s16le")

    def test_rejects_empty_audio(self) -> None:
        response = self.client.post(
            "/transcribe",
            files={"file": ("speech.wav", b"", "audio/wav")},
            data={"language_code": "hi-IN"},
        )
        self.assertEqual(response.status_code, 400)


class SarvamServiceTests(unittest.TestCase):
    def test_maps_sdk_response(self) -> None:
        class FakeResponse:
            transcript = "Hello world"
            language_code = "en-IN"

        class FakeClient:
            class speech_to_text:
                @staticmethod
                def transcribe(**kwargs):
                    return FakeResponse()

        service = SarvamSTTService(Settings(sarvam_api_key="test-key"), client=FakeClient())
        self.assertEqual(
            service.transcribe(audio=b"audio", filename="test.webm", content_type="audio/webm", language_code="en-IN"),
            ("Hello world", "en-IN"),
        )

    def test_forwards_pcm_codec_to_sdk(self) -> None:
        class FakeResponse:
            transcript = "Hello world"
            language_code = "en-IN"

        class FakeClient:
            class speech_to_text:
                call = None

                @classmethod
                def transcribe(cls, **kwargs):
                    cls.call = kwargs
                    return FakeResponse()

        service = SarvamSTTService(Settings(sarvam_api_key="test-key"), client=FakeClient())
        service.transcribe(
            audio=b"audio",
            filename="test.pcm",
            content_type="audio/pcm",
            language_code="en-IN",
            input_audio_codec="pcm_s16le",
        )
        self.assertEqual(FakeClient.speech_to_text.call["input_audio_codec"], "pcm_s16le")

    def test_requires_backend_key(self) -> None:
        service = SarvamSTTService(Settings(_env_file=None))
        with self.assertRaises(SarvamTranscriptionError) as context:
            service.transcribe(audio=b"audio", filename="test.wav", content_type="audio/wav", language_code="hi-IN")
        self.assertEqual(context.exception.status_code, 500)


class VoiceRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        class FakeSTT:
            def __init__(self, language_code: str) -> None:
                self.language_code = language_code
                self.calls = []

            def transcribe(self, **kwargs):
                self.calls.append(kwargs)
                return "spoken question", self.language_code

        class FakeAnswerService:
            def __init__(self) -> None:
                self.calls = []

            def generate_response(self, transcript: str, language_code: str) -> str:
                self.calls.append((transcript, language_code))
                return "generated response"

        class FakeTTS:
            def __init__(self) -> None:
                self.calls = []

            def synthesize(self, *, text: str, language_code: str):
                self.calls.append((text, language_code))
                return "YmFzZTY0LWF1ZGlv", "audio/mpeg"

        self.fake_stt = FakeSTT("hi-IN")
        self.fake_answer = FakeAnswerService()
        self.fake_tts = FakeTTS()
        app.dependency_overrides[get_settings] = lambda: Settings(sarvam_api_key="test-key")
        app.dependency_overrides[get_stt_service] = lambda: self.fake_stt
        from app.main import get_answer_service, get_tts_service

        app.dependency_overrides[get_answer_service] = lambda: self.fake_answer
        app.dependency_overrides[get_tts_service] = lambda: self.fake_tts
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_health_still_works(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_voice_audio_only_runs_complete_pipeline(self) -> None:
        response = self.client.post(
            "/voice", files={"file": ("question.webm", b"audio", "audio/webm")}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "transcript": "spoken question",
                "language_code": "hi-IN",
                "response_text": "generated response",
                "response_audio": "YmFzZTY0LWF1ZGlv",
                "audio_content_type": "audio/mpeg",
            },
        )
        self.assertEqual(self.fake_stt.calls[0]["language_code"], "unknown")
        self.assertEqual(self.fake_answer.calls, [("spoken question", "hi-IN")])
        self.assertEqual(self.fake_tts.calls, [("generated response", "hi-IN")])

    def test_voice_rejects_missing_audio(self) -> None:
        response = self.client.post("/voice")
        self.assertEqual(response.status_code, 422)

    def test_voice_requires_main_application_answer_service(self) -> None:
        from app.main import get_answer_service

        app.dependency_overrides.pop(get_answer_service)
        response = self.client.post(
            "/voice", files={"file": ("question.webm", b"audio", "audio/webm")}
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("answer generation is not configured", response.json()["detail"].lower())

    def test_voice_preserves_initial_languages(self) -> None:
        for language_code in ("en-IN", "hi-IN", "te-IN"):
            with self.subTest(language_code=language_code):
                self.fake_stt.language_code = language_code
                response = self.client.post(
                    "/voice", files={"file": ("question.webm", b"audio", "audio/webm")}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["language_code"], language_code)
                self.assertEqual(self.fake_tts.calls[-1][1], language_code)

    def test_voice_returns_clear_unsupported_tts_language_error(self) -> None:
        self.fake_stt.language_code = "as-IN"
        from app.main import get_tts_service

        app.dependency_overrides[get_tts_service] = lambda: SarvamTTSService(
            Settings(sarvam_api_key="test-key"), client=object()
        )
        response = self.client.post(
            "/voice", files={"file": ("question.webm", b"audio", "audio/webm")}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("spoken output is currently unavailable", response.json()["detail"].lower())


class TTSServiceTests(unittest.TestCase):
    def test_maps_base64_audio_and_uses_bulbul_v3(self) -> None:
        class FakeResponse:
            audios = ["YmFzZTY0LWF1ZGlv"]

        class FakeClient:
            class text_to_speech:
                call = None

                @classmethod
                def convert(cls, **kwargs):
                    cls.call = kwargs
                    return FakeResponse()

        service = SarvamTTSService(Settings(sarvam_api_key="test-key"), client=FakeClient())
        self.assertEqual(
            service.synthesize(text="Namaste", language_code="hi-IN"),
            ("YmFzZTY0LWF1ZGlv", "audio/mpeg"),
        )
        self.assertEqual(FakeClient.text_to_speech.call["model"], "bulbul:v3")

    def test_rejects_language_not_supported_by_tts(self) -> None:
        service = SarvamTTSService(Settings(sarvam_api_key="test-key"), client=object())
        with self.assertRaises(SarvamTextToSpeechError) as context:
            service.synthesize(text="text", language_code="as-IN")
        self.assertEqual(context.exception.status_code, 422)

    def test_tts_requires_backend_key(self) -> None:
        service = SarvamTTSService(Settings(_env_file=None))
        with self.assertRaises(SarvamTextToSpeechError) as context:
            service.synthesize(text="text", language_code="hi-IN")
        self.assertEqual(context.exception.status_code, 500)

    def test_tts_sarvam_rate_limit_is_safe(self) -> None:
        class RateLimitedClient:
            class text_to_speech:
                @staticmethod
                def convert(**kwargs):
                    raise ApiError(status_code=429, body={"message": "internal detail"})

        service = SarvamTTSService(
            Settings(sarvam_api_key="test-key"), client=RateLimitedClient()
        )
        with self.assertRaises(SarvamTextToSpeechError) as context:
            service.synthesize(text="text", language_code="hi-IN")
        self.assertEqual(context.exception.status_code, 503)
        self.assertNotIn("internal detail", context.exception.message)


if __name__ == "__main__":
    unittest.main()

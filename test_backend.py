import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import backend
from ai.schemas import FormField, FormSchema


def test_health_and_answer_persistence(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        backend.database = backend.Database(Path(directory) / "test.db")
        form = FormSchema(
            form_name="Test form",
            fields=[
                FormField(
                    id="name",
                    label="Name",
                    type="text",
                    required=True,
                    options=[],
                    explanation="Your name",
                    confidence="high",
                )
            ],
        )
        image_path = Path(directory) / "form.png"
        image_path.write_bytes(b"image")
        backend.database.save_form("form-1", form, image_path)
        client = TestClient(backend.app)

        assert client.get("/health").json()["status"] == "ok"
        response = client.post(
            "/forms/form-1/answers",
            json={"field_id": "name", "value": "Asha", "confirmed": True},
        )
        assert response.status_code == 200
        submission = client.post("/forms/form-1/submit")
        assert submission.status_code == 200
        assert submission.json()["answers"] == {"name": "Asha"}
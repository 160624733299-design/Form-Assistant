"""FastAPI traffic controller for form analysis, speech, and persistence."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Iterator
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from ai.form_analyzer import FormAnalysisError, analyze_form
from ai.question_flow import validate_answer
from ai.schemas import FormSchema


ROOT = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("FORM_ASSISTANT_DB", ROOT / "form_assistant.db"))
UPLOAD_DIRECTORY = ROOT / "uploads"


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    value: str
    confirmed: bool = False


class SubmissionResponse(BaseModel):
    submission_id: int
    form_id: str
    answers: dict[str, str]


class Database:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS forms (
                    id TEXT PRIMARY KEY,
                    form_name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    schema_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    form_id TEXT NOT NULL REFERENCES forms(id),
                    field_id TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confirmed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(form_id, field_id)
                );
                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    form_id TEXT NOT NULL REFERENCES forms(id),
                    answers_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_form(self, form_id: str, form: FormSchema, image_path: Path) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO forms VALUES (?, ?, ?, ?, ?)",
                (form_id, form.form_name, str(image_path), form.model_dump_json(), _now()),
            )

    def get_form(self, form_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM forms WHERE id = ?", (form_id,)).fetchone()

    def save_answer(self, form_id: str, answer: AnswerRequest) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO answers(form_id, field_id, value, confirmed, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(form_id, field_id) DO UPDATE SET
                    value = excluded.value,
                    confirmed = excluded.confirmed,
                    created_at = excluded.created_at
                """,
                (form_id, answer.field_id, answer.value, int(answer.confirmed), _now()),
            )

    def get_answers(self, form_id: str, confirmed_only: bool = False) -> dict[str, str]:
        query = "SELECT field_id, value FROM answers WHERE form_id = ?"
        parameters: tuple[Any, ...] = (form_id,)
        if confirmed_only:
            query += " AND confirmed = 1"
        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return {row["field_id"]: row["value"] for row in rows}

    def save_submission(self, form_id: str, answers: dict[str, str]) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO submissions(form_id, answers_json, created_at) VALUES (?, ?, ?)",
                (form_id, json.dumps(answers, ensure_ascii=False), _now()),
            )
            return int(cursor.lastrowid)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


database = Database()
app = FastAPI(title="Form Assistant Integration API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_sarvam_service() -> Any:
    from sarvam_stt_module.app.config import get_settings
    from sarvam_stt_module.app.service import SarvamSTTService

    return SarvamSTTService(get_settings())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "form-assistant-backend"}


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(ROOT / "index.html", media_type="text/html")


@app.post("/forms/analyze")
async def analyze_uploaded_form(file: Annotated[UploadFile, File(...)]) -> dict[str, Any]:
    suffix = Path(file.filename or "form.png").suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, WEBP, or GIF image.")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    image_path = UPLOAD_DIRECTORY / f"{uuid4().hex}{suffix}"
    image_path.write_bytes(image_bytes)
    try:
        result = analyze_form(str(image_path))
    except FormAnalysisError as error:
        image_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not isinstance(result, FormSchema):
        image_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=result.message)
    form_id = uuid4().hex
    database.save_form(form_id, result, image_path)
    return {"form_id": form_id, "form": result.model_dump()}


@app.get("/forms/{form_id}")
def get_form(form_id: str) -> dict[str, Any]:
    row = database.get_form(form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    return {"form_id": form_id, "form": json.loads(row["schema_json"]), "answers": database.get_answers(form_id)}


@app.post("/forms/{form_id}/answers")
def save_form_answer(form_id: str, answer: AnswerRequest) -> dict[str, Any]:
    row = database.get_form(form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    form = FormSchema.model_validate_json(row["schema_json"])
    field = next((item for item in form.fields if item.id == answer.field_id), None)
    if field is None:
        raise HTTPException(status_code=404, detail="Field not found in this form.")
    validation = validate_answer(field, answer.value)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.message)
    database.save_answer(form_id, answer)
    return {"field_id": answer.field_id, "value": answer.value, "confirmed": answer.confirmed}


@app.post("/forms/{form_id}/submit", response_model=SubmissionResponse)
def submit_form(form_id: str) -> SubmissionResponse:
    row = database.get_form(form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    form = FormSchema.model_validate_json(row["schema_json"])
    answers = database.get_answers(form_id, confirmed_only=True)
    missing = [field.label for field in form.fields if field.required and field.id not in answers]
    if missing:
        raise HTTPException(status_code=422, detail=f"Confirm required fields: {', '.join(missing)}")
    submission_id = database.save_submission(form_id, answers)
    return SubmissionResponse(submission_id=submission_id, form_id=form_id, answers=answers)


@app.post("/voice/transcribe")
async def transcribe_voice(
    file: Annotated[UploadFile, File(...)],
    service: Any = Depends(get_sarvam_service),
) -> dict[str, str | None]:
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="The uploaded audio is empty.")
    try:
        transcript, language_code = service.transcribe(
            audio=audio,
            filename=file.filename or "audio.webm",
            content_type=file.content_type,
            language_code="unknown",
        )
    except Exception as error:
        status_code = getattr(error, "status_code", 502)
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    return {"transcript": transcript, "language_code": language_code}
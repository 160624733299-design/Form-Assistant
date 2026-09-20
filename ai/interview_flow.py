"""In-memory, confirmation-first collection of answers for an extracted form."""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .question_flow import FormQuestion, question_for_field
from .schemas import FormField, FormSchema

ValidationResult = tuple[bool, str | None]
AnswerValidator = Callable[[FormField, str], ValidationResult]


class AnswerReview(BaseModel):
    """A validated answer waiting for the user's explicit confirmation."""

    model_config = ConfigDict(extra="forbid")

    field_id: str
    value: str
    status: Literal["needs_confirmation", "invalid"]
    message: str | None = None


class FormInterview:
    """Collect answers in order without persisting or writing them onto a form."""

    def __init__(self, form: FormSchema, validate_answer: AnswerValidator) -> None:
        self._form = form
        self._validate_answer = validate_answer
        self._confirmed_answers: dict[str, str] = {}
        self._pending_answer: AnswerReview | None = None

    def next_question(self) -> FormQuestion | None:
        """Return the next field question, unless an answer needs confirmation."""

        if self._pending_answer is not None:
            return None
        for field in self._form.fields:
            if field.id not in self._confirmed_answers:
                return question_for_field(field)
        return None

    def submit_answer(self, value: str) -> AnswerReview:
        """Validate an answer and present it for confirmation; do not save it yet."""

        if self._pending_answer is not None:
            raise ValueError("Confirm or reject the current answer before submitting another one.")
        question = self.next_question()
        if question is None:
            raise ValueError("All visible form fields have already been confirmed.")

        field = next(field for field in self._form.fields if field.id == question.field_id)
        is_valid, message = self._validate_answer(field, value)
        if not is_valid:
            return AnswerReview(
                field_id=field.id,
                value=value,
                status="invalid",
                message=message or "Please provide that information again.",
            )

        self._pending_answer = AnswerReview(
            field_id=field.id,
            value=value,
            status="needs_confirmation",
            message=message,
        )
        return self._pending_answer

    def confirm_answer(self, confirmed: bool) -> None:
        """Keep a pending answer only after the user explicitly confirms it."""

        if self._pending_answer is None:
            raise ValueError("There is no answer awaiting confirmation.")
        if confirmed:
            self._confirmed_answers[self._pending_answer.field_id] = self._pending_answer.value
        self._pending_answer = None

    def confirmed_answers(self) -> dict[str, str]:
        """Return a copy of answers confirmed in this in-memory interview."""

        return self._confirmed_answers.copy()

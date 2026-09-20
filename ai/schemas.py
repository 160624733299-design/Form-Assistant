"""Strict data contracts for form-image extraction."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FieldType = Literal["text", "date", "phone", "number", "email", "radio", "checkbox", "textarea"]
Confidence = Literal["high", "medium"]
ValueFormat = Literal["email", "numeric", "name", "date"]


class ValidationMetadata(BaseModel):
    """Rules Qwen can tie to visible form content or an unambiguous field type.

    These are extracted facts, not an AI validation decision. The deterministic
    backend decides which rules to enforce.
    """

    model_config = ConfigDict(extra="forbid")

    value_format: ValueFormat | None = None
    numeric_only: bool | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    exact_length: int | None = Field(default=None, ge=0)
    date_format: str | None = None
    instructions: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    confidence: Confidence = "medium"
    uncertain: bool = False


class FormField(BaseModel):
    """One field visibly present on the printed form."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="Deterministic lowercase ID derived from the visible label.")
    label: str = Field(description="Visible field label only; never reconstruct unreadable text.")
    type: FieldType
    required: bool = Field(description="True only with visible required evidence.")
    options: list[str] = Field(description="Only visibly printed choices; otherwise empty.")
    explanation: str = Field(description="Simple explanation limited to visible information.")
    confidence: Confidence = Field(description="Medium only when reliable; otherwise return unclear.")
    expected_digits: int | None = Field(
        default=None,
        description="Exact digit count only when explicitly printed next to this field; otherwise null.",
    )
    visible_instructions: list[str] = Field(
        default_factory=list,
        description="Short notes or input instructions visibly printed for this field; otherwise empty.",
    )
    validation: ValidationMetadata = Field(
        default_factory=ValidationMetadata,
        description="Structured validation metadata extracted only from visible form content or unambiguous field type.",
    )


class FormSchema(BaseModel):
    """A reliably readable form; this is extraction output, never answer validation."""
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"] = "ok"
    form_name: str = Field(description="Visible form title only. Never invent one.")
    fields: list[FormField]


class UnclearResult(BaseModel):
    """Explicit result used instead of partial or guessed extraction."""
    model_config = ConfigDict(extra="forbid")
    status: Literal["unclear"]
    message: str


AnalysisResult = FormSchema | UnclearResult

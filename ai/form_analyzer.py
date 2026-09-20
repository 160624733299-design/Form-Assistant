"""Qwen vision extraction through OpenRouter."""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

from .schemas import AnalysisResult, FormField, FormSchema, UnclearResult

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "qwen/qwen3.8-flash"
MALFORMED_RESPONSE_ATTEMPTS = 2

EXTRACTION_INSTRUCTIONS = """
Extract a physical printed form from the supplied image. Return one JSON object.
This is extraction, not answer validation. Use status 'ok' only if every
material visible element can be reliably read and structured without guessing.
Copy only visible text and choices. Never add fields, labels, options, required
flags, titles, requirements, explanations, values, or eligibility decisions.
For an ID, derive stable lowercase snake_case from the visible label. Mark a
field required only with explicit visible evidence (for example, * or required).
Otherwise set it false. Use a field type only when printed structure supports
it; generic text is permitted only when safe. Keep explanations simple and
limited to visible information. If any material text is unreadable, the image
is blurred, cropped, dark, distorted, title-less, or ambiguous, return status
'unclear' with a concise request for a clearer image. Never return a partial form.

Return exactly one top-level object. Do not wrap it inside `form` or another
object. Always include these four keys: `status`, `form_name`, `fields`, and
`message`. For status `ok`, use the visible title in `form_name`, provide the
fields, and set `message` to an empty string. For status `unclear`, set
`form_name` to an empty string, `fields` to an empty list, and provide the
clarification message.

Set expected_digits only if an exact digit count is visibly printed for that
specific field (for example, '(10 digits)'). Otherwise set it to null. This is
visible-structure extraction only, not validation.

Copy any other short, field-specific note or input instruction that is visibly
printed into visible_instructions. Do not create, paraphrase, or infer notes.

For every field, populate validation metadata from the actual visible form:
value_format, numeric_only, min_length, max_length, exact_length, date_format,
instructions, examples, and dependencies. Set a value only when it is visibly
printed or is an unambiguous consequence of the extracted field type/label
(for example, an Email ID field has value_format 'email'; Full Name has
value_format 'name'). Do not infer any government, service, eligibility, or
common Indian-form requirement. The uploaded form is always the source of
truth, even if its terminology resembles an Indian service or application.

You may use knowledge of Indian form terminology only to understand a visible
label or instruction; never turn a convention into a requirement that is not
shown. Mark validation.uncertain true and use no aggressive rule when a
constraint cannot be read reliably. Use validation.confidence high only for a
clearly visible or unambiguous rule. This extraction does not decide whether a
user answer is valid.
""".strip()


class FormAnalysisError(RuntimeError):
    """An actionable local, API, or malformed-response failure."""


class _ExtractionEnvelope(BaseModel):
    """A single-root transport contract for model structured output.

    The public result remains the existing FormSchema | UnclearResult union
    after local Pydantic conversion.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "unclear"]
    form_name: str
    fields: list[FormField]
    message: str


def _load_image_data_url(image_path: str) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise FormAnalysisError(f"Image file not found: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if mime_type not in allowed_types:
        raise FormAnalysisError("Unsupported or unrecognised image type. Use JPEG, PNG, WEBP, or GIF.")
    try:
        image_bytes = path.read_bytes()
    except OSError as error:
        raise FormAnalysisError(f"Could not read image file: {error}") from error
    if not image_bytes:
        raise FormAnalysisError("Image file is empty.")
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded_image}"


def _parse_response(raw_text: object) -> AnalysisResult:
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise FormAnalysisError("Qwen returned no structured response.")
    try:
        envelope = _ExtractionEnvelope.model_validate_json(raw_text)
    except ValidationError as error:
        raise FormAnalysisError(f"Qwen returned malformed structured data: {error}") from error
    if envelope.status == "ok":
        if not envelope.form_name:
            raise FormAnalysisError("Qwen returned an understood form without a visible form name.")
        if envelope.message:
            raise FormAnalysisError("Qwen returned an unexpected message with an understood form.")
        return FormSchema(form_name=envelope.form_name, fields=envelope.fields)
    if not envelope.message:
        raise FormAnalysisError("Qwen returned an unclear result without an explanation.")
    if envelope.fields or envelope.form_name:
        raise FormAnalysisError("Qwen returned form content with an unclear result.")
    return UnclearResult(status="unclear", message=envelope.message)


def analyze_form(image_path: str) -> AnalysisResult:
    """Extract a reliable form, or return UnclearResult for an unreliable photo."""
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise FormAnalysisError("OPENROUTER_API_KEY is missing. Add it to .env or the environment.")
    image_data_url = _load_image_data_url(image_path)
    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)
    last_error: FormAnalysisError | None = None
    for _ in range(MALFORMED_RESPONSE_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": EXTRACTION_INSTRUCTIONS},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze this form image and return the required JSON object."},
                            {"type": "image_url", "image_url": {"url": image_data_url}},
                        ],
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "physical_form_analysis",
                        "strict": True,
                        "schema": _ExtractionEnvelope.model_json_schema(),
                    },
                },
                temperature=0,
                max_tokens=2048,
                extra_body={"provider": {"require_parameters": True}},
            )
        except Exception as error:
            raise FormAnalysisError(f"OpenRouter Qwen request failed: {error}") from error
        if not response.choices:
            raise FormAnalysisError("OpenRouter Qwen returned no choices.")
        try:
            return _parse_response(response.choices[0].message.content)
        except FormAnalysisError as error:
            last_error = error

    raise FormAnalysisError(
        "Qwen returned malformed structured data after two attempts. Please try the image again. "
        f"Last error: {last_error}"
    )

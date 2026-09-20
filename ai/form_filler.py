"""Locate visible form entry areas and render a reference-only filled copy."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .form_analyzer import DEFAULT_MODEL, MALFORMED_RESPONSE_ATTEMPTS, OPENROUTER_BASE_URL, _load_image_data_url
from .question_flow import AnswerSession
from .schemas import FormSchema


class FormFillError(RuntimeError):
    """An actionable field-location or reference-rendering error."""


class FillBox(BaseModel):
    """Normalized coordinates of a blank area where a confirmed value belongs."""

    model_config = ConfigDict(extra="forbid")

    field_id: str
    left: int = Field(ge=0, le=1000)
    top: int = Field(ge=0, le=1000)
    right: int = Field(ge=0, le=1000)
    bottom: int = Field(ge=0, le=1000)
    confidence: Literal["high"]


class PlacementResult(BaseModel):
    """Reliable field locations, or an explicit request for a clearer image."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "unclear"]
    message: str | None = None
    boxes: list[FillBox] = Field(default_factory=list)


LOCATION_INSTRUCTIONS = """
Locate the blank entry areas in the supplied physical form image. This is only
location extraction, not validation and not answer filling.

For every requested field, return the rectangle of the EMPTY area where a user
would write their value, not the label, not a checkbox label, and not a note.
Coordinates must be normalized to the original image: left/top/right/bottom
are integers from 0 to 1000, where 0 is the left/top edge and 1000 is the
right/bottom edge. Return confidence 'high' only when the matching blank area
is clearly visible and unambiguous.

If any requested field cannot be located reliably because the form is unclear,
cropped, has no visible entry area, or the field-to-area match is ambiguous,
return status 'unclear', an explanation, and no boxes. Never invent a box.
Return only the required JSON object.
""".strip()


def locate_fill_boxes(image_path: str, form: FormSchema, answer_session: AnswerSession) -> PlacementResult:
    """Ask Qwen to locate every confirmed answer's visible blank area."""

    if answer_session.form_name != form.form_name:
        raise FormFillError("The confirmed answers do not belong to this form.")
    answer_ids = [answer.field_id for answer in answer_session.answers]
    known_fields = {field.id: field for field in form.fields}
    if not answer_ids:
        raise FormFillError("There are no confirmed answers to place on the form.")
    if any(field_id not in known_fields for field_id in answer_ids):
        raise FormFillError("A confirmed answer refers to a field not found in the extracted form.")

    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise FormFillError("OPENROUTER_API_KEY is missing. Add it to .env or the environment.")

    requested_fields = [
        {"field_id": field_id, "label": known_fields[field_id].label}
        for field_id in answer_ids
    ]
    image_data_url = _load_image_data_url(image_path)
    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)
    last_error: FormFillError | None = None

    for _ in range(MALFORMED_RESPONSE_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": LOCATION_INSTRUCTIONS},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Locate entry areas for these fields only: " + str(requested_fields),
                            },
                            {"type": "image_url", "image_url": {"url": image_data_url}},
                        ],
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "physical_form_fill_locations",
                        "strict": True,
                        "schema": PlacementResult.model_json_schema(),
                    },
                },
                temperature=0,
                max_tokens=2048,
                extra_body={"provider": {"require_parameters": True}},
            )
        except Exception as error:
            raise FormFillError(f"OpenRouter Qwen location request failed: {error}") from error
        if not response.choices:
            raise FormFillError("OpenRouter Qwen returned no location choices.")
        try:
            result = PlacementResult.model_validate_json(response.choices[0].message.content)
            return _validate_placements(result, answer_ids)
        except (ValidationError, FormFillError) as error:
            last_error = FormFillError(f"Qwen returned malformed field locations: {error}")

    raise FormFillError(
        "Qwen could not return reliable field locations after two attempts. "
        f"Last error: {last_error}"
    )


def _validate_placements(result: PlacementResult, answer_ids: list[str]) -> PlacementResult:
    if result.status == "unclear":
        if not result.message:
            raise FormFillError("Qwen returned an unclear location result without an explanation.")
        if result.boxes:
            raise FormFillError("An unclear location result must not include placement boxes.")
        return result
    if result.message is not None:
        raise FormFillError("A successful location result must not include an unclear message.")
    box_ids = [box.field_id for box in result.boxes]
    if len(box_ids) != len(set(box_ids)):
        raise FormFillError("Qwen returned duplicate field locations.")
    if set(box_ids) != set(answer_ids):
        raise FormFillError("Qwen did not locate exactly the confirmed form fields.")
    for box in result.boxes:
        if box.left >= box.right or box.top >= box.bottom:
            raise FormFillError(f"Qwen returned an invalid placement box for {box.field_id}.")
    return result


def render_filled_reference(image_path: str, answer_session: AnswerSession, placements: PlacementResult) -> bytes:
    """Render confirmed values onto a copy; the source image is never modified."""

    if placements.status != "ok":
        raise FormFillError(placements.message or "The form fields could not be located reliably.")
    answer_by_id = {answer.field_id: answer.value for answer in answer_session.answers}
    try:
        image = Image.open(image_path).convert("RGB")
    except (OSError, ValueError) as error:
        raise FormFillError(f"Could not open the form image for rendering: {error}") from error

    draw = ImageDraw.Draw(image)
    for box in placements.boxes:
        value = answer_by_id[box.field_id]
        pixel_box = _to_pixel_box(box, image.width, image.height)
        font = _font_to_fit(draw, value, pixel_box)
        if font is None:
            raise FormFillError(f"The confirmed value for {box.field_id} does not fit its visible entry area.")
        left, top, _, _ = pixel_box
        draw.text((left, top), value, fill="#00E5FF", font=font, stroke_width=1, stroke_fill="#000000")

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _to_pixel_box(box: FillBox, width: int, height: int) -> tuple[int, int, int, int]:
    return (
        round(width * box.left / 1000),
        round(height * box.top / 1000),
        round(width * box.right / 1000),
        round(height * box.bottom / 1000),
    )


def _font_to_fit(draw: ImageDraw.ImageDraw, value: str, pixel_box: tuple[int, int, int, int]) -> ImageFont.ImageFont | ImageFont.FreeTypeFont | None:
    left, top, right, bottom = pixel_box
    available_width = right - left
    available_height = bottom - top
    for size in range(max(8, available_height), 7, -1):
        font = _load_font(size)
        text_box = draw.textbbox((0, 0), value, font=font, stroke_width=1)
        if text_box[2] - text_box[0] <= available_width and text_box[3] - text_box[1] <= available_height:
            return font
    return None


def _load_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for font_path in ("C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()

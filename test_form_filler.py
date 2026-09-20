"""Local rendering checks; field location is tested live through the Streamlit flow."""

from pathlib import Path

from PIL import Image

from ai.form_filler import FillBox, PlacementResult, render_filled_reference
from ai.question_flow import AnswerSession, ConfirmedAnswer


def main() -> None:
    source = Path("sample_form.png")
    session = AnswerSession(
        form_name="SERVICE REQUEST FORM",
        answers=[ConfirmedAnswer(field_id="full_name", value="Asha Kumar")],
    )
    placements = PlacementResult(
        status="ok",
        boxes=[FillBox(field_id="full_name", left=250, top=390, right=900, bottom=480, confidence="high")],
    )
    output = render_filled_reference(str(source), session, placements)
    assert output.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(source) as original, Image.open(__import__("io").BytesIO(output)) as rendered:
        assert rendered.size == original.size
    print("Reference rendering test passed.")


if __name__ == "__main__":
    main()

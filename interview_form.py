"""Terminal-only prototype: analyze a form, then collect confirmed user input."""

import json
from pathlib import Path

from ai.form_analyzer import FormAnalysisError, analyze_form
from ai.question_flow import collect_confirmed_answers
from ai.schemas import FormSchema

SAMPLE_IMAGE = Path("sample_form.png")


def main() -> None:
    if not SAMPLE_IMAGE.is_file():
        print("ERROR: sample_form.png was not found.")
        return
    try:
        result = analyze_form(str(SAMPLE_IMAGE))
    except FormAnalysisError as error:
        print(f"ERROR: {error}")
        return
    if not isinstance(result, FormSchema):
        print(f"Unclear: {result.message}")
        return

    print(f"I found: {result.form_name}")
    print("I will ask about each visible field. Please confirm every answer before it is kept.")
    try:
        session = collect_confirmed_answers(result)
    except EOFError:
        print("\nInterview stopped before all answers were confirmed. Nothing was saved.")
        return
    print("\nConfirmed answers (not validated or saved):")
    print(json.dumps(session.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

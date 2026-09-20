"""Manual OpenRouter Qwen vision and physical-form extraction smoke test."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from ai.form_analyzer import FormAnalysisError, analyze_form
from ai.question_flow import instruction_for_field, next_question
from ai.schemas import FormSchema

SAMPLE_IMAGE = Path("sample_form.png")


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY is missing. Set it in .env before testing.")
        return
    if not SAMPLE_IMAGE.is_file():
        print("SKIPPED: sample_form.png was not found. Add a clear real printed-form photo at the project root.")
        return
    try:
        result = analyze_form(str(SAMPLE_IMAGE))
    except FormAnalysisError as error:
        print(f"ERROR: {error}")
        return
    if isinstance(result, FormSchema):
        print(f"Form name: {result.form_name}")
        for field in result.fields:
            print(f"ID: {field.id}\nLabel: {field.label}\nType: {field.type}\nRequired: {field.required}")
            print(f"Options: {field.options}\nExplanation: {field.explanation}\nConfidence: {field.confidence}")
            print(f"Instruction: {instruction_for_field(field)}")
        print("\nQuestions to ask:")
        answered_field_ids: set[str] = set()
        while question := next_question(result, answered_field_ids):
            print(f"{question.field_id}: {question.prompt}")
            answered_field_ids.add(question.field_id)
    else:
        print(f"Unclear: {result.message}")
    print("\nFinal JSON:")
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

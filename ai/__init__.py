"""AI extraction package for Accessible India."""

from .form_analyzer import analyze_form
from .form_filler import locate_fill_boxes, render_filled_reference
from .interview_flow import FormInterview
from .question_flow import AnswerSession, AnswerValidation, ConfirmedAnswer, FormQuestion, collect_confirmed_answers, explain_field, instruction_for_field, next_question, question_for_field, validate_answer
from .schemas import FormSchema, UnclearResult

__all__ = [
    "analyze_form",
    "AnswerSession",
    "AnswerValidation",
    "ConfirmedAnswer",
    "collect_confirmed_answers",
    "explain_field",
    "instruction_for_field",
    "locate_fill_boxes",
    "FormInterview",
    "FormQuestion",
    "FormSchema",
    "UnclearResult",
    "next_question",
    "question_for_field",
    "render_filled_reference",
    "validate_answer",
]

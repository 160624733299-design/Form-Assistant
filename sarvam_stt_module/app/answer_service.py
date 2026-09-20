"""Boundary for the main application's answer-generation implementation.

This module deliberately contains no chatbot, LLM, or business-answer logic.
"""

from typing import Protocol


class AnswerGenerationUnavailable(Exception):
    """Raised until the main application supplies its answer-generation service."""


class AnswerService(Protocol):
    def generate_response(self, transcript: str, language_code: str) -> str:
        """Return answer text in the supplied language."""


class UnconfiguredAnswerService:
    """Safe default: prevents this speech module from inventing application answers."""

    def generate_response(self, transcript: str, language_code: str) -> str:
        raise AnswerGenerationUnavailable(
            "Answer generation is not configured. The main application must provide an AnswerService."
        )

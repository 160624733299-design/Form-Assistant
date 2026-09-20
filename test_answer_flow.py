"""Local deterministic tests for user-answer help, validation, and confirmation."""

from ai.question_flow import collect_confirmed_answers, explain_field, instruction_for_field, validate_answer
from ai.schemas import FormField, FormSchema, ValidationMetadata


def field(field_type: str, **values: object) -> FormField:
    defaults: dict[str, object] = {
        "id": "field",
        "label": "Field:",
        "type": field_type,
        "required": False,
        "options": [],
        "explanation": "This is an explanation of the visible field.",
        "confidence": "high",
    }
    defaults.update(values)
    return FormField(**defaults)


def main() -> None:
    assert not validate_answer(field("phone", expected_digits=10), "987654321").valid
    assert validate_answer(field("phone", expected_digits=10), "9876543210").valid
    assert validate_answer(field("phone"), "123").valid  # No count is visibly specified for this field.
    assert not validate_answer(field("email"), "name@gmail").valid
    assert validate_answer(field("email"), "name@gmail.com").valid
    assert not validate_answer(field("number"), "ten").valid
    assert not validate_answer(field("date"), "May").valid
    assert validate_answer(field("date"), "20/09/2026").valid
    assert not validate_answer(field("radio", options=["Phone", "Email"]), "Text").valid
    assert validate_answer(field("checkbox", options=["SMS", "Email"]), "SMS, Email").valid
    constrained_id = field(
        "text",
        validation=ValidationMetadata(min_length=4, max_length=6, confidence="high"),
    )
    assert not validate_answer(constrained_id, "123").valid
    assert not validate_answer(constrained_id, "1234567").valid
    assert validate_answer(constrained_id, "12345").valid
    uncertain_constraint = field(
        "text",
        validation=ValidationMetadata(exact_length=10, confidence="medium", uncertain=True),
    )
    assert validate_answer(uncertain_constraint, "abc").valid

    service_form = FormSchema(
        form_name="SERVICE REQUEST FORM",
        fields=[
            field("text", id="full_name", label="Full Name", explanation="Text field for entering the full name."),
            field(
                "phone",
                id="mobile_number",
                label="Mobile Number",
                explanation="Phone number field.",
                expected_digits=10,
                visible_instructions=["(10 digits)"],
                validation=ValidationMetadata(exact_length=10, numeric_only=True, confidence="high"),
            ),
            field("phone", id="alternative_number", label="Alternative Number", explanation="Phone number field."),
            field("email", id="email_id", label="Email ID", explanation="Email address field."),
        ],
    )
    service_form.fields[0].validation = ValidationMetadata(value_format="name", confidence="high")
    assert "Please enter Full Name." in instruction_for_field(service_form.fields[0])
    assert "letters and spaces" in instruction_for_field(service_form.fields[0])
    assert not validate_answer(service_form.fields[0], "9").valid
    assert not validate_answer(service_form.fields[0], "Asha9 Kumar").valid
    assert validate_answer(service_form.fields[0], "Asha Kumar").valid
    assert "exactly 10 digits" in instruction_for_field(service_form.fields[1])
    assert "phone number" in instruction_for_field(service_form.fields[2]).casefold()
    assert "name@example.com" in instruction_for_field(service_form.fields[3])
    assert "Email address field." in explain_field(service_form.fields[3], "what is this?")

    service_responses = iter(
        [
            "what should I enter?", "9", "Asha Kumar", "no", "Asha Patel", "yes",
            "987654321", "9876543210", "y",
            "what is this?", "abc", "9876543", "yes",
            "what does this field mean?", "asha@gmail", "asha@gmail.com", "yeah",
        ]
    )
    service_messages: list[str] = []
    service_session = collect_confirmed_answers(
        service_form,
        input_fn=lambda _: next(service_responses),
        output_fn=service_messages.append,
    )
    assert [answer.value for answer in service_session.answers] == [
        "Asha Patel", "9876543210", "9876543", "asha@gmail.com"
    ]
    assert all(answer.value not in {"9", "Asha Kumar", "what should I enter?", "what is this?"} for answer in service_session.answers)
    assert any("do not enter digits" in message for message in service_messages)
    assert any("10 digits" in message for message in service_messages)
    assert any("email in the format" in message for message in service_messages)
    assert "Please enter the value again." in service_messages

    form = FormSchema(form_name="Test Form", fields=[field("phone", expected_digits=10)])
    responses = iter(["what is this?", "987654321", "9876543210", "what does this field mean?", "maybe", "yeah"])
    messages: list[str] = []
    session = collect_confirmed_answers(form, input_fn=lambda _: next(responses), output_fn=messages.append)
    assert session.answers[0].value == "9876543210"
    assert "This is an explanation of the visible field." in messages
    assert any("10 digits" in message for message in messages)
    assert "Please answer yes or no." in messages
    print("Answer help, validation, correction, and confirmation tests passed.")


if __name__ == "__main__":
    main()

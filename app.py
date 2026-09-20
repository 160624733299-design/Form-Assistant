"""Temporary Streamlit UI for Accessible India form analysis and reference filling."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

import streamlit as st

from ai.form_analyzer import FormAnalysisError, analyze_form
from ai.form_filler import FormFillError, locate_fill_boxes, render_filled_reference
from ai.question_flow import AnswerSession, ConfirmedAnswer, explain_field, instruction_for_field, validate_answer
from ai.schemas import FormSchema


st.set_page_config(page_title="Accessible India — Form Assistant", layout="wide")
st.title("Accessible India — Form Assistant")
st.caption("Upload a printed form, answer one field at a time, then download a reference copy. Your original image is not changed.")


def _temporary_image(upload: st.runtime.uploaded_file_manager.UploadedFile) -> str:
    suffix = Path(upload.name).suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
        temporary_file.write(upload.getvalue())
        return temporary_file.name


def _clear_flow() -> None:
    for key in ("form", "image_path", "field_index", "answers", "pending_value", "reference_png", "location_error"):
        st.session_state.pop(key, None)


def _input_for_field(field: object) -> str:
    # Streamlit controls are selected solely from the extracted field structure.
    if getattr(field, "type") == "textarea":
        return st.text_area("Your answer", key=f"input_{field.id}")
    if getattr(field, "type") == "checkbox" and getattr(field, "options"):
        return ", ".join(st.multiselect("Choose visible options", field.options, key=f"input_{field.id}"))
    if getattr(field, "options"):
        return st.selectbox("Choose a visible option", [""] + field.options, key=f"input_{field.id}")
    return st.text_input("Your answer", key=f"input_{field.id}")


upload = st.file_uploader("Upload a clear form image", type=["png", "jpg", "jpeg", "webp", "gif"])
if upload and st.button("Analyze form", type="primary"):
    _clear_flow()
    image_path = _temporary_image(upload)
    try:
        analysis = analyze_form(image_path)
    except FormAnalysisError as error:
        os.unlink(image_path)
        st.error(str(error))
    else:
        if isinstance(analysis, FormSchema):
            st.session_state.form = analysis
            st.session_state.image_path = image_path
            st.session_state.field_index = 0
            st.session_state.answers = {}
        else:
            os.unlink(image_path)
            st.warning(analysis.message)

form = st.session_state.get("form")
if isinstance(form, FormSchema):
    image_path = st.session_state.image_path
    left_column, right_column = st.columns(2)
    with left_column:
        st.image(image_path, caption="Original form (unchanged)", use_container_width=True)
    with right_column:
        index = st.session_state.field_index
        if index < len(form.fields):
            field = form.fields[index]
            st.subheader(f"Field {index + 1} of {len(form.fields)}: {field.label}")
            st.write(field.explanation)
            st.info(instruction_for_field(field))

            user_question = st.text_input("Ask about this field (optional)", key=f"question_{field.id}")
            if st.button("Explain this field", key=f"explain_{field.id}") and user_question.strip():
                st.write(explain_field(field, user_question))

            pending = st.session_state.get("pending_value")
            if pending is None:
                value = _input_for_field(field)
                if st.button("Check answer", key=f"check_{field.id}", type="primary"):
                    validation = validate_answer(field, value)
                    if validation.valid:
                        st.session_state.pending_value = value
                        st.rerun()
                    else:
                        st.error(validation.message or "Please correct this value.")
            else:
                st.write(f"You entered: `{pending}`")
                st.write("Is this correct?")
                confirm_column, edit_column = st.columns(2)
                if confirm_column.button("Yes, keep it", type="primary"):
                    st.session_state.answers[field.id] = pending
                    st.session_state.field_index += 1
                    st.session_state.pop("pending_value", None)
                    st.rerun()
                if edit_column.button("No, edit it"):
                    st.session_state.pop("pending_value", None)
                    st.rerun()
        else:
            st.success("All answers are confirmed. Create a reference copy when ready.")
            answers = AnswerSession(
                form_name=form.form_name,
                answers=[ConfirmedAnswer(field_id=field.id, value=st.session_state.answers[field.id]) for field in form.fields],
            )
            if st.button("Create filled reference copy", type="primary"):
                try:
                    placements = locate_fill_boxes(image_path, form, answers)
                    if placements.status == "unclear":
                        st.warning(placements.message)
                    else:
                        st.session_state.reference_png = render_filled_reference(image_path, answers, placements)
                except FormFillError as error:
                    st.error(str(error))

            reference_png = st.session_state.get("reference_png")
            if reference_png:
                st.image(reference_png, caption="Filled reference copy — review before copying onto a physical form", use_container_width=True)
                st.download_button("Download reference PNG", reference_png, "filled_form_reference.png", "image/png")

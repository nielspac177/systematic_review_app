"""Risk of Bias judgment form component for domain assessment."""

import streamlit as st
from typing import Optional, Callable

from core.storage.models import (
    RoBDomainTemplate, RoBDomainJudgment, SignalingQuestionResponse,
    JudgmentLevel, StudyRoBAssessment
)
from core.risk_of_bias.visualization import JUDGMENT_COLORS, JUDGMENT_LABELS


def render_signaling_question(
    question,
    response: Optional[SignalingQuestionResponse] = None,
    key_prefix: str = "",
    editable: bool = True,
) -> SignalingQuestionResponse:
    """
    Render a single signaling question form.

    Args:
        question: SignalingQuestion object
        response: Optional existing response
        key_prefix: Prefix for widget keys
        editable: Whether the form is editable

    Returns:
        SignalingQuestionResponse with user input
    """
    st.markdown(f"**{question.question_text}**")

    if question.guidance:
        st.caption(question.guidance)

    current_response = response.response if response else None
    current_quote = response.supporting_quote if response else ""
    current_notes = response.notes if response else ""

    if editable:
        selected = st.radio(
            "Response",
            options=question.response_options,
            index=question.response_options.index(current_response) if current_response in question.response_options else 0,
            key=f"{key_prefix}_response_{question.id}",
            horizontal=True,
        )

        quote = st.text_area(
            "Supporting quote from text",
            value=current_quote or "",
            key=f"{key_prefix}_quote_{question.id}",
            height=80,
        )

        notes = st.text_input(
            "Notes (optional)",
            value=current_notes or "",
            key=f"{key_prefix}_notes_{question.id}",
        )
    else:
        st.markdown(f"Response: **{current_response or 'Not assessed'}**")
        if current_quote:
            st.markdown(f"> {current_quote}")
        if current_notes:
            st.caption(f"Notes: {current_notes}")

        selected = current_response
        quote = current_quote
        notes = current_notes

    return SignalingQuestionResponse(
        question_id=question.id,
        response=selected or "No Information",
        supporting_quote=quote if quote else None,
        notes=notes if notes else None,
    )


def render_domain_judgment_form(
    domain: RoBDomainTemplate,
    existing_judgment: Optional[RoBDomainJudgment] = None,
    key_prefix: str = "",
    editable: bool = True,
    show_ai_suggestion: bool = True,
) -> Optional[RoBDomainJudgment]:
    """
    Render a complete domain judgment form.

    Args:
        domain: Domain template
        existing_judgment: Optional existing judgment to display/edit
        key_prefix: Prefix for widget keys
        editable: Whether the form is editable
        show_ai_suggestion: Whether to show AI suggestion if available

    Returns:
        RoBDomainJudgment with user input, or None if cancelled
    """
    # Domain header with status indicator
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader(domain.name)
    with col2:
        if existing_judgment:
            color = JUDGMENT_COLORS.get(existing_judgment.judgment, "#808080")
            label = JUDGMENT_LABELS.get(existing_judgment.judgment, "Unknown")
            st.markdown(
                f'<span style="background-color: {color}; padding: 4px 8px; border-radius: 4px; border: 1px solid #333;">'
                f'{label}</span>',
                unsafe_allow_html=True
            )

    st.caption(domain.description)

    # Show AI suggestion if available
    if show_ai_suggestion and existing_judgment and existing_judgment.ai_suggested_judgment:
        ai_color = JUDGMENT_COLORS.get(existing_judgment.ai_suggested_judgment, "#808080")
        ai_label = JUDGMENT_LABELS.get(existing_judgment.ai_suggested_judgment, "Unknown")
        confidence = existing_judgment.ai_confidence or 0
        confidence_pct = f"{confidence * 100:.0f}%"

        st.info(
            f"AI Suggestion: **{ai_label}** (Confidence: {confidence_pct})"
        )

        if existing_judgment.is_flagged_uncertain:
            st.warning("This domain has been flagged for human review due to low AI confidence.")

    # Signaling questions
    signaling_responses = []

    existing_responses = {}
    if existing_judgment:
        existing_responses = {sr.question_id: sr for sr in existing_judgment.signaling_responses}

    st.markdown("### Signaling Questions")

    for i, question in enumerate(domain.signaling_questions):
        with st.container():
            existing_response = existing_responses.get(question.id)
            response = render_signaling_question(
                question,
                response=existing_response,
                key_prefix=f"{key_prefix}_{domain.id}_{i}",
                editable=editable,
            )
            signaling_responses.append(response)
            st.divider()

    # Domain-level judgment
    st.markdown("### Domain Judgment")

    # Show guidance
    if domain.judgment_guidance:
        with st.expander("Judgment guidance"):
            for level, guidance in domain.judgment_guidance.items():
                st.markdown(f"**{level.replace('_', ' ').title()}**: {guidance}")

    # Determine available judgment options based on domain
    judgment_options = [
        JudgmentLevel.LOW,
        JudgmentLevel.SOME_CONCERNS,
        JudgmentLevel.HIGH,
    ]

    # ROBINS-I uses different levels
    if any(level in domain.judgment_guidance for level in ["moderate", "serious", "critical"]):
        judgment_options = [
            JudgmentLevel.LOW,
            JudgmentLevel.MODERATE,
            JudgmentLevel.SERIOUS,
            JudgmentLevel.CRITICAL,
        ]

    # QUADAS-2 uses Low/High/Unclear
    if "unclear" in (domain.judgment_guidance or {}):
        judgment_options = [
            JudgmentLevel.LOW,
            JudgmentLevel.HIGH,
            JudgmentLevel.UNCLEAR,
        ]

    current_judgment = existing_judgment.judgment if existing_judgment else JudgmentLevel.UNCLEAR

    if editable:
        judgment_labels = [JUDGMENT_LABELS.get(j, j.value) for j in judgment_options]
        current_index = judgment_options.index(current_judgment) if current_judgment in judgment_options else 0

        selected_label = st.selectbox(
            "Judgment",
            options=judgment_labels,
            index=current_index,
            key=f"{key_prefix}_{domain.id}_judgment",
        )

        selected_judgment = judgment_options[judgment_labels.index(selected_label)]

        rationale = st.text_area(
            "Rationale",
            value=existing_judgment.rationale if existing_judgment else "",
            key=f"{key_prefix}_{domain.id}_rationale",
            height=100,
            help="Explain the basis for your judgment, referencing the signaling question responses."
        )

        supporting_quotes_str = st.text_area(
            "Key supporting quotes (one per line)",
            value="\n".join(existing_judgment.supporting_quotes) if existing_judgment else "",
            key=f"{key_prefix}_{domain.id}_quotes",
            height=80,
        )
        supporting_quotes = [q.strip() for q in supporting_quotes_str.split("\n") if q.strip()]

        # Human verification checkbox
        is_verified = st.checkbox(
            "Mark as human-verified",
            value=existing_judgment.is_human_verified if existing_judgment else False,
            key=f"{key_prefix}_{domain.id}_verified",
        )

        override_notes = None
        if existing_judgment and selected_judgment != existing_judgment.ai_suggested_judgment:
            override_notes = st.text_input(
                "Override notes (explain why you disagree with AI)",
                key=f"{key_prefix}_{domain.id}_override",
            )
    else:
        selected_judgment = current_judgment
        rationale = existing_judgment.rationale if existing_judgment else ""
        supporting_quotes = existing_judgment.supporting_quotes if existing_judgment else []
        is_verified = existing_judgment.is_human_verified if existing_judgment else False
        override_notes = existing_judgment.human_override_notes if existing_judgment else None

        st.markdown(f"**Judgment:** {JUDGMENT_LABELS.get(selected_judgment, 'Unknown')}")
        if rationale:
            st.markdown(f"**Rationale:** {rationale}")
        if supporting_quotes:
            st.markdown("**Supporting quotes:**")
            for quote in supporting_quotes:
                st.markdown(f"> {quote}")

    return RoBDomainJudgment(
        id=existing_judgment.id if existing_judgment else None,
        domain_id=domain.id,
        domain_name=domain.name,
        signaling_responses=signaling_responses,
        judgment=selected_judgment,
        rationale=rationale,
        supporting_quotes=supporting_quotes,
        ai_suggested_judgment=existing_judgment.ai_suggested_judgment if existing_judgment else None,
        ai_confidence=existing_judgment.ai_confidence if existing_judgment else None,
        is_ai_generated=existing_judgment.is_ai_generated if existing_judgment else False,
        is_human_verified=is_verified,
        is_flagged_uncertain=False,  # Clear flag when manually assessed
        human_override_notes=override_notes,
    )


def render_assessment_form(
    template,
    assessment: Optional[StudyRoBAssessment] = None,
    key_prefix: str = "",
    on_save: Optional[Callable[[StudyRoBAssessment], None]] = None,
) -> None:
    """
    Render a complete assessment form with all domains.

    Args:
        template: RoBTemplate
        assessment: Optional existing assessment
        key_prefix: Prefix for widget keys
        on_save: Optional callback when assessment is saved
    """
    st.markdown(f"### {template.name}")
    st.caption(template.description)

    # Track which domains are expanded
    if f"{key_prefix}_expanded" not in st.session_state:
        st.session_state[f"{key_prefix}_expanded"] = set()

    domain_judgments = []
    existing_judgments = {}
    if assessment:
        existing_judgments = {dj.domain_id: dj for dj in assessment.domain_judgments}

    for domain in sorted(template.domains, key=lambda d: d.display_order):
        existing_judgment = existing_judgments.get(domain.id)

        # Show summary in expander header
        status = ""
        if existing_judgment:
            if existing_judgment.is_human_verified:
                status = " - Verified"
            elif existing_judgment.is_flagged_uncertain:
                status = " - Needs Review"
            else:
                status = " - AI Assessed"

        with st.expander(f"{domain.short_name}{status}", expanded=domain.id in st.session_state[f"{key_prefix}_expanded"]):
            judgment = render_domain_judgment_form(
                domain,
                existing_judgment=existing_judgment,
                key_prefix=key_prefix,
            )
            domain_judgments.append(judgment)

    # Overall judgment section
    st.markdown("---")
    st.markdown("### Overall Judgment")

    if assessment:
        st.markdown(f"Current: **{JUDGMENT_LABELS.get(assessment.overall_judgment, 'Unknown')}**")
        if assessment.overall_rationale:
            st.markdown(f"Rationale: {assessment.overall_rationale}")

    # Save button
    if st.button("Save Assessment", type="primary", key=f"{key_prefix}_save"):
        if on_save and assessment:
            assessment.domain_judgments = domain_judgments
            on_save(assessment)
            st.success("Assessment saved!")

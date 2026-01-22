"""Risk of Bias summary table component."""

import streamlit as st
import pandas as pd
from typing import Optional, Callable

from core.storage.models import StudyRoBAssessment, Study, JudgmentLevel
from core.risk_of_bias.visualization import (
    create_summary_table, JUDGMENT_COLORS, JUDGMENT_LABELS,
    get_domain_distribution
)


def render_rob_summary_table(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
    on_study_click: Optional[Callable[[str], None]] = None,
    show_details: bool = True,
) -> None:
    """
    Render an interactive summary table of RoB assessments.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies for details
        on_study_click: Optional callback when study is clicked
        show_details: Whether to show detailed domain columns
    """
    if not assessments:
        st.info("No assessments to display")
        return

    df = create_summary_table(assessments, studies)

    # Style the dataframe
    def color_judgment(val):
        """Apply color based on judgment value."""
        judgment_map = {v: k for k, v in JUDGMENT_LABELS.items()}
        level = judgment_map.get(val)
        if level:
            color = JUDGMENT_COLORS.get(level, "#ffffff")
            return f'background-color: {color}'
        return ''

    # Get columns to style (judgment columns)
    domain_cols = [col for col in df.columns if col not in ['Study ID', 'Study', 'Authors', 'Year', 'Tool', 'Status', 'Flagged', 'Verified']]

    # Apply styling
    styled_df = df.style.applymap(color_judgment, subset=domain_cols)

    # Display
    if show_details:
        st.dataframe(styled_df, use_container_width=True, height=400)
    else:
        # Show simplified table
        simple_cols = ['Study', 'Year', 'Overall Judgment', 'Status', 'Verified']
        available_cols = [c for c in simple_cols if c in df.columns]
        st.dataframe(df[available_cols], use_container_width=True)

    # Selection for navigation
    if on_study_click:
        st.markdown("---")
        selected_study = st.selectbox(
            "Select a study to view/edit",
            options=df['Study ID'].tolist(),
            format_func=lambda x: df[df['Study ID'] == x]['Study'].values[0] if len(df[df['Study ID'] == x]) > 0 else x,
        )
        if st.button("View Assessment"):
            on_study_click(selected_study)


def render_domain_summary(assessments: list[StudyRoBAssessment]) -> None:
    """
    Render a summary of judgments by domain.

    Args:
        assessments: List of RoB assessments
    """
    if not assessments:
        return

    distribution = get_domain_distribution(assessments)

    for domain_name, judgments in distribution.items():
        with st.expander(domain_name):
            cols = st.columns(len(judgments) + 1)
            total = sum(judgments.values())

            with cols[0]:
                st.metric("Total", total)

            for i, (judgment, count) in enumerate(judgments.items(), 1):
                with cols[i]:
                    pct = count / total * 100 if total > 0 else 0
                    st.metric(judgment, count, f"{pct:.0f}%")


def render_flagged_items(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
    on_review_click: Optional[Callable[[str, str], None]] = None,
) -> None:
    """
    Render a list of flagged items requiring review.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies
        on_review_click: Optional callback(study_id, domain_id)
    """
    study_map = {}
    if studies:
        study_map = {s.id: s for s in studies}

    flagged_items = []

    for assessment in assessments:
        for dj in assessment.domain_judgments:
            if dj.is_flagged_uncertain and not dj.is_human_verified:
                study = study_map.get(assessment.study_id)
                flagged_items.append({
                    "study_id": assessment.study_id,
                    "study_title": study.title[:50] if study else assessment.study_id,
                    "domain_id": dj.domain_id,
                    "domain_name": dj.domain_name,
                    "ai_judgment": JUDGMENT_LABELS.get(dj.ai_suggested_judgment, "Unknown"),
                    "confidence": f"{(dj.ai_confidence or 0) * 100:.0f}%",
                })

    if not flagged_items:
        st.success("No items flagged for review")
        return

    st.warning(f"{len(flagged_items)} item(s) require human review")

    for item in flagged_items:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                st.markdown(f"**{item['study_title']}**")
                st.caption(f"Domain: {item['domain_name']}")

            with col2:
                st.markdown(f"AI: {item['ai_judgment']} ({item['confidence']})")

            with col3:
                if on_review_click:
                    if st.button("Review", key=f"review_{item['study_id']}_{item['domain_id']}"):
                        on_review_click(item['study_id'], item['domain_id'])

            st.divider()


def render_verification_progress(assessments: list[StudyRoBAssessment]) -> None:
    """
    Render verification progress metrics.

    Args:
        assessments: List of RoB assessments
    """
    if not assessments:
        return

    total_domains = sum(len(a.domain_judgments) for a in assessments)
    verified_domains = sum(
        sum(1 for dj in a.domain_judgments if dj.is_human_verified)
        for a in assessments
    )
    flagged_domains = sum(
        sum(1 for dj in a.domain_judgments if dj.is_flagged_uncertain and not dj.is_human_verified)
        for a in assessments
    )

    # Studies with all domains verified
    fully_verified = sum(
        1 for a in assessments
        if all(dj.is_human_verified for dj in a.domain_judgments)
    )

    cols = st.columns(4)

    with cols[0]:
        st.metric("Total Studies", len(assessments))

    with cols[1]:
        st.metric("Fully Verified", fully_verified, f"/{len(assessments)}")

    with cols[2]:
        pct = verified_domains / total_domains * 100 if total_domains > 0 else 0
        st.metric("Domains Verified", verified_domains, f"{pct:.0f}%")

    with cols[3]:
        st.metric("Needs Review", flagged_domains)

    # Progress bar
    if total_domains > 0:
        st.progress(verified_domains / total_domains)


def render_export_options(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
) -> None:
    """
    Render export options for RoB data.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies
    """
    st.markdown("### Export Options")

    col1, col2, col3 = st.columns(3)

    df = create_summary_table(assessments, studies)

    with col1:
        csv = df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            csv,
            "rob_summary.csv",
            "text/csv",
            use_container_width=True,
        )

    with col2:
        try:
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='RoB Summary')
            buffer.seek(0)

            st.download_button(
                "Download Excel",
                buffer,
                "rob_summary.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except ImportError:
            st.button("Download Excel", disabled=True, use_container_width=True)
            st.caption("Install openpyxl for Excel export")

    with col3:
        # Placeholder for DOCX export
        st.button("Download Report (DOCX)", disabled=True, use_container_width=True)
        st.caption("Coming soon")

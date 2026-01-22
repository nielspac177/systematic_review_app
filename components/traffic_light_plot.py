"""Traffic light plot component for Risk of Bias visualization."""

import streamlit as st
from typing import Optional

from core.storage.models import StudyRoBAssessment, Study, JudgmentLevel
from core.risk_of_bias.visualization import (
    TrafficLightPlot, JUDGMENT_COLORS, JUDGMENT_LABELS, JUDGMENT_SYMBOLS,
    create_distribution_chart, get_judgment_distribution
)


def render_traffic_light_plot(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
    include_overall: bool = True,
    height: Optional[int] = None,
) -> None:
    """
    Render an interactive traffic light plot using Plotly.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies for labels
        include_overall: Whether to include overall judgment column
        height: Optional custom height
    """
    if not assessments:
        st.info("No assessments to display")
        return

    try:
        plot = TrafficLightPlot(assessments, studies)
        fig = plot.create_plotly_figure(include_overall=include_overall)

        if height:
            fig.update_layout(height=height)

        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.warning("Plotly not installed. Install with: pip install plotly")
        # Fall back to simple table
        render_rob_table_simple(assessments, studies)


def render_rob_table_simple(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
) -> None:
    """
    Render a simple colored table without Plotly.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies for labels
    """
    if not assessments:
        st.info("No assessments to display")
        return

    study_map = {}
    if studies:
        study_map = {s.id: s for s in studies}

    # Build HTML table
    html = ['<table style="border-collapse: collapse; width: 100%;">']

    # Header
    domains = [dj.domain_name for dj in assessments[0].domain_judgments]
    html.append('<tr style="background-color: #f0f0f0;">')
    html.append('<th style="border: 1px solid #ddd; padding: 8px;">Study</th>')
    for domain in domains:
        html.append(f'<th style="border: 1px solid #ddd; padding: 8px; writing-mode: vertical-rl; text-orientation: mixed;">{domain}</th>')
    html.append('<th style="border: 1px solid #ddd; padding: 8px;">Overall</th>')
    html.append('</tr>')

    # Rows
    for assessment in assessments:
        study = study_map.get(assessment.study_id)
        label = study.title[:40] if study else assessment.study_id[:20]

        html.append('<tr>')
        html.append(f'<td style="border: 1px solid #ddd; padding: 8px;">{label}</td>')

        for dj in assessment.domain_judgments:
            color = JUDGMENT_COLORS.get(dj.judgment, "#808080")
            symbol = JUDGMENT_SYMBOLS.get(dj.judgment, "?")
            html.append(f'<td style="border: 1px solid #ddd; padding: 8px; background-color: {color}; text-align: center; font-weight: bold;">{symbol}</td>')

        # Overall
        color = JUDGMENT_COLORS.get(assessment.overall_judgment, "#808080")
        symbol = JUDGMENT_SYMBOLS.get(assessment.overall_judgment, "?")
        html.append(f'<td style="border: 1px solid #ddd; padding: 8px; background-color: {color}; text-align: center; font-weight: bold;">{symbol}</td>')

        html.append('</tr>')

    html.append('</table>')

    st.markdown(''.join(html), unsafe_allow_html=True)


def render_judgment_legend() -> None:
    """Render a legend for the judgment colors and symbols."""
    st.markdown("**Legend:**")

    cols = st.columns(5)
    legend_items = [
        (JudgmentLevel.LOW, "Low Risk", "+"),
        (JudgmentLevel.SOME_CONCERNS, "Some Concerns", "?"),
        (JudgmentLevel.HIGH, "High Risk", "-"),
        (JudgmentLevel.UNCLEAR, "Unclear", "?"),
    ]

    for i, (level, label, symbol) in enumerate(legend_items):
        color = JUDGMENT_COLORS.get(level, "#808080")
        with cols[i % len(cols)]:
            st.markdown(
                f'<span style="background-color: {color}; padding: 4px 8px; border-radius: 4px; border: 1px solid #333;">'
                f'<strong>{symbol}</strong></span> {label}',
                unsafe_allow_html=True
            )


def render_distribution_chart(
    assessments: list[StudyRoBAssessment],
    chart_type: str = "bar",
) -> None:
    """
    Render a distribution chart for overall judgments.

    Args:
        assessments: List of assessments
        chart_type: "bar" or "pie"
    """
    if not assessments:
        st.info("No assessments to display")
        return

    try:
        fig = create_distribution_chart(assessments, chart_type)
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        # Fall back to simple metrics
        distribution = get_judgment_distribution(assessments)
        cols = st.columns(len(distribution))
        for i, (label, count) in enumerate(distribution.items()):
            with cols[i]:
                st.metric(label, count)


def render_rob_summary_metrics(assessments: list[StudyRoBAssessment]) -> None:
    """
    Render summary metrics for RoB assessments.

    Args:
        assessments: List of assessments
    """
    if not assessments:
        return

    distribution = get_judgment_distribution(assessments)
    total = len(assessments)

    cols = st.columns(4)

    with cols[0]:
        st.metric("Total Assessed", total)

    with cols[1]:
        low_risk = distribution.get("Low Risk", 0)
        st.metric("Low Risk", low_risk, f"{low_risk/total*100:.0f}%" if total > 0 else "0%")

    with cols[2]:
        some_concerns = distribution.get("Some Concerns", 0) + distribution.get("Moderate", 0)
        st.metric("Some Concerns", some_concerns)

    with cols[3]:
        high_risk = distribution.get("High Risk", 0) + distribution.get("Serious", 0) + distribution.get("Critical", 0)
        st.metric("High Risk", high_risk)

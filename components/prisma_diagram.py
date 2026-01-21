"""PRISMA 2020 flow diagram component for Streamlit."""

import streamlit as st
from typing import Optional
import json

from core.storage.models import PRISMACounts


def render_prisma_box(
    label: str,
    count: int,
    sublabel: Optional[str] = None,
    color: str = "#e3f2fd",
    width: str = "200px",
) -> str:
    """
    Render a single PRISMA box as HTML.

    Args:
        label: Main label text
        count: Count to display
        sublabel: Optional sublabel
        color: Background color
        width: Box width

    Returns:
        HTML string for the box
    """
    sublabel_html = f'<div style="font-size: 10px; color: #666;">{sublabel}</div>' if sublabel else ""
    return f"""
    <div style="
        background-color: {color};
        border: 2px solid #1976d2;
        border-radius: 8px;
        padding: 12px;
        margin: 5px;
        text-align: center;
        width: {width};
        display: inline-block;
        vertical-align: top;
    ">
        <div style="font-weight: bold; font-size: 14px;">{label}</div>
        <div style="font-size: 24px; color: #1976d2; font-weight: bold;">{count:,}</div>
        {sublabel_html}
    </div>
    """


def render_arrow(direction: str = "down", label: str = "") -> str:
    """
    Render an arrow between boxes.

    Args:
        direction: "down", "right", or "left"
        label: Optional label on arrow

    Returns:
        HTML string for the arrow
    """
    if direction == "down":
        return f"""
        <div style="text-align: center; margin: 5px 0;">
            <div style="font-size: 10px; color: #666;">{label}</div>
            <div style="font-size: 24px; color: #1976d2;">↓</div>
        </div>
        """
    elif direction == "right":
        return f"""
        <span style="display: inline-block; vertical-align: middle; margin: 0 10px;">
            <span style="font-size: 10px; color: #666;">{label}</span>
            <span style="font-size: 24px; color: #1976d2;">→</span>
        </span>
        """
    return ""


def render_prisma_diagram(counts: PRISMACounts) -> None:
    """
    Render full PRISMA 2020 flow diagram in Streamlit.

    Args:
        counts: PRISMACounts object with all counts
    """
    st.markdown("### PRISMA 2020 Flow Diagram")

    # Custom CSS for the diagram
    st.markdown("""
    <style>
    .prisma-section {
        margin: 20px 0;
        padding: 15px;
        border-left: 4px solid #1976d2;
    }
    .prisma-section-title {
        font-weight: bold;
        color: #1976d2;
        margin-bottom: 10px;
        font-size: 16px;
    }
    .prisma-row {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-wrap: wrap;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # IDENTIFICATION
    st.markdown('<div class="prisma-section"><div class="prisma-section-title">IDENTIFICATION</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        st.markdown(render_prisma_box(
            "Records identified from databases",
            counts.records_identified_databases,
            color="#e3f2fd"
        ), unsafe_allow_html=True)

    with col2:
        st.markdown("<div style='text-align: center; padding-top: 30px;'>+</div>", unsafe_allow_html=True)

    with col3:
        st.markdown(render_prisma_box(
            "Records from registers",
            counts.records_identified_registers,
            color="#e3f2fd"
        ), unsafe_allow_html=True)

    st.markdown(render_arrow("down"), unsafe_allow_html=True)

    # Total and duplicates
    total_identified = counts.records_identified_databases + counts.records_identified_registers

    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        st.markdown(render_prisma_box(
            "Total records identified",
            total_identified,
            color="#bbdefb"
        ), unsafe_allow_html=True)

    with col2:
        st.markdown(render_arrow("right"), unsafe_allow_html=True)

    with col3:
        st.markdown(render_prisma_box(
            "Duplicates removed",
            counts.records_removed_duplicates,
            color="#ffcdd2"
        ), unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # SCREENING
    st.markdown(render_arrow("down"), unsafe_allow_html=True)
    st.markdown('<div class="prisma-section"><div class="prisma-section-title">SCREENING</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        st.markdown(render_prisma_box(
            "Records screened",
            counts.records_screened,
            "(Title/Abstract)",
            color="#e8f5e9"
        ), unsafe_allow_html=True)

    with col2:
        st.markdown(render_arrow("right"), unsafe_allow_html=True)

    with col3:
        st.markdown(render_prisma_box(
            "Records excluded",
            counts.records_excluded_screening,
            color="#ffcdd2"
        ), unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ELIGIBILITY
    st.markdown(render_arrow("down"), unsafe_allow_html=True)
    st.markdown('<div class="prisma-section"><div class="prisma-section-title">ELIGIBILITY</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        st.markdown(render_prisma_box(
            "Reports sought for retrieval",
            counts.reports_sought,
            color="#fff3e0"
        ), unsafe_allow_html=True)

    with col2:
        st.markdown(render_arrow("right"), unsafe_allow_html=True)

    with col3:
        st.markdown(render_prisma_box(
            "Reports not retrieved",
            counts.reports_not_retrieved,
            color="#ffcdd2"
        ), unsafe_allow_html=True)

    st.markdown(render_arrow("down"), unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        st.markdown(render_prisma_box(
            "Reports assessed for eligibility",
            counts.reports_assessed,
            "(Full-text)",
            color="#fff3e0"
        ), unsafe_allow_html=True)

    with col2:
        st.markdown(render_arrow("right"), unsafe_allow_html=True)

    with col3:
        st.markdown(render_prisma_box(
            "Reports excluded",
            counts.reports_excluded,
            color="#ffcdd2"
        ), unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # INCLUDED
    st.markdown(render_arrow("down"), unsafe_allow_html=True)
    st.markdown('<div class="prisma-section"><div class="prisma-section-title">INCLUDED</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="text-align: center;">{render_prisma_box("Studies included in review", counts.studies_included, color="#c8e6c9", width="250px")}</div>',
        unsafe_allow_html=True
    )

    st.markdown('</div>', unsafe_allow_html=True)

    # Exclusion reasons breakdown
    if counts.exclusion_reasons:
        st.markdown("### Exclusion Reasons Breakdown")

        # Create a simple table
        reasons_data = []
        for reason, count in sorted(counts.exclusion_reasons.items(), key=lambda x: -x[1]):
            reasons_data.append({"Reason": reason.replace("_", " ").title(), "Count": count})

        if reasons_data:
            st.table(reasons_data)


def render_prisma_mini(counts: PRISMACounts) -> None:
    """
    Render a compact PRISMA summary for sidebar.

    Args:
        counts: PRISMACounts object
    """
    total = counts.records_identified_databases + counts.records_identified_registers

    st.markdown("**PRISMA Summary**")

    metrics = [
        ("Identified", total),
        ("After duplicates", total - counts.records_removed_duplicates),
        ("After screening", counts.records_screened - counts.records_excluded_screening),
        ("Included", counts.studies_included),
    ]

    for label, value in metrics:
        st.markdown(f"- {label}: **{value:,}**")


def update_prisma_counts(
    counts: PRISMACounts,
    phase: str,
    included: int = 0,
    excluded: int = 0,
    exclusion_reasons: Optional[dict] = None,
) -> PRISMACounts:
    """
    Update PRISMA counts based on screening results.

    Args:
        counts: Current PRISMACounts
        phase: Phase being updated
        included: Number included
        excluded: Number excluded
        exclusion_reasons: Optional dict of reason -> count

    Returns:
        Updated PRISMACounts
    """
    if phase == "identification":
        counts.records_identified_databases = included

    elif phase == "duplicates":
        counts.records_removed_duplicates = excluded

    elif phase == "title_abstract":
        counts.records_screened = included + excluded
        counts.records_excluded_screening = excluded
        counts.reports_sought = included

    elif phase == "retrieval":
        counts.reports_not_retrieved = excluded
        counts.reports_assessed = included

    elif phase == "fulltext":
        counts.reports_assessed = included + excluded
        counts.reports_excluded = excluded
        counts.studies_included = included

    # Update exclusion reasons
    if exclusion_reasons:
        for reason, count in exclusion_reasons.items():
            current = counts.exclusion_reasons.get(reason, 0)
            counts.exclusion_reasons[reason] = current + count

    return counts

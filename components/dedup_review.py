"""Deduplication review UI component."""

import streamlit as st
from typing import Optional, Callable
import pandas as pd

from core.storage.models import DeduplicationResult, ParsedReference


def render_dedup_statistics(result: DeduplicationResult) -> None:
    """
    Render deduplication statistics overview.

    Args:
        result: DeduplicationResult object
    """
    st.markdown("### Deduplication Summary")

    # Main metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Records",
            result.total_records,
        )

    with col2:
        st.metric(
            "Unique Records",
            result.unique_records,
            delta=f"-{result.duplicate_count} duplicates",
            delta_color="normal",
        )

    with col3:
        dup_rate = (result.duplicate_count / result.total_records * 100) if result.total_records > 0 else 0
        st.metric(
            "Duplicate Rate",
            f"{dup_rate:.1f}%",
        )

    with col4:
        st.metric(
            "Sources",
            len(result.records_per_source),
        )

    # Records per source
    st.markdown("### Records by Source")

    source_data = []
    for source, count in result.records_per_source.items():
        source_data.append({"Source": source, "Records": count})

    if source_data:
        df = pd.DataFrame(source_data)
        st.bar_chart(df.set_index("Source"))

    # Duplicate breakdown
    st.markdown("### Duplicate Detection Methods")

    method_col1, method_col2, method_col3 = st.columns(3)

    with method_col1:
        st.metric("DOI Match", result.doi_duplicates)

    with method_col2:
        st.metric("Fuzzy Title Match", result.title_fuzzy_duplicates)

    with method_col3:
        st.metric("Title+Author+Year", result.title_author_year_duplicates)


def render_dedup_table(
    result: DeduplicationResult,
    show_duplicates_only: bool = False,
    on_toggle_duplicate: Optional[Callable[[str, bool], None]] = None,
    page_size: int = 20,
) -> None:
    """
    Render reference table with duplicate status.

    Args:
        result: DeduplicationResult object
        show_duplicates_only: Only show duplicates
        on_toggle_duplicate: Callback to toggle duplicate status
        page_size: Number of records per page
    """
    # Filter references
    if show_duplicates_only:
        refs = [r for r in result.all_references if r.is_duplicate]
        st.info(f"Showing {len(refs)} duplicates")
    else:
        refs = result.all_references

    if not refs:
        st.info("No records to display")
        return

    # Convert to dataframe for display
    data = []
    for ref in refs:
        data.append({
            "ID": ref.id[:8],
            "Title": ref.title[:80] + "..." if len(ref.title) > 80 else ref.title,
            "Authors": (ref.authors[:40] + "...") if ref.authors and len(ref.authors) > 40 else (ref.authors or "-"),
            "Year": ref.year or "-",
            "Source": ref.source_database,
            "Duplicate": "Yes" if ref.is_duplicate else "No",
            "Reason": ref.duplicate_reason or "-",
            "Score": f"{ref.duplicate_score:.2f}" if ref.duplicate_score else "-",
        })

    df = pd.DataFrame(data)

    # Pagination
    total_pages = (len(df) + page_size - 1) // page_size
    page = st.number_input(
        "Page",
        min_value=1,
        max_value=max(1, total_pages),
        value=1,
        key="dedup_page",
    )

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, len(df))

    st.caption(f"Showing records {start_idx + 1}-{end_idx} of {len(df)}")

    # Display table
    st.dataframe(
        df.iloc[start_idx:end_idx],
        use_container_width=True,
        hide_index=True,
    )


def render_duplicate_review(
    duplicate_groups: list[list[ParsedReference]],
    on_keep: Optional[Callable[[str], None]] = None,
    on_merge: Optional[Callable[[list[str]], None]] = None,
) -> None:
    """
    Render interface for reviewing duplicate groups.

    Args:
        duplicate_groups: List of duplicate groups
        on_keep: Callback when selecting which record to keep
        on_merge: Callback when merging records
    """
    st.markdown("### Review Duplicates")

    if not duplicate_groups:
        st.success("No duplicates to review!")
        return

    st.info(f"Found {len(duplicate_groups)} duplicate groups to review")

    for i, group in enumerate(duplicate_groups):
        with st.expander(f"Group {i + 1}: {len(group)} records", expanded=i == 0):
            # Show all records in group
            for j, ref in enumerate(group):
                is_master = j == 0

                col1, col2 = st.columns([4, 1])

                with col1:
                    badge = "🏆 Master" if is_master else f"📄 Duplicate ({ref.duplicate_reason})"
                    st.markdown(f"**{badge}**")
                    st.markdown(f"**Title:** {ref.title}")

                    if ref.authors:
                        st.markdown(f"**Authors:** {ref.authors}")

                    details = []
                    if ref.year:
                        details.append(f"Year: {ref.year}")
                    if ref.doi:
                        details.append(f"DOI: {ref.doi}")
                    if ref.pmid:
                        details.append(f"PMID: {ref.pmid}")
                    if ref.source_database:
                        details.append(f"Source: {ref.source_database}")

                    if details:
                        st.caption(" | ".join(details))

                with col2:
                    if on_keep:
                        if st.button("Keep This", key=f"keep_{ref.id}"):
                            on_keep(ref.id)

                st.divider()

            if on_merge and len(group) > 1:
                if st.button(f"Merge Group {i + 1}", key=f"merge_{i}"):
                    on_merge([r.id for r in group])


def render_file_upload_section(
    on_upload: Callable[[list], None],
    accepted_types: list[str] = None,
) -> None:
    """
    Render file upload section for reference files.

    Args:
        on_upload: Callback with list of uploaded files
        accepted_types: Accepted file extensions
    """
    if accepted_types is None:
        accepted_types = [".ris", ".nbib", ".txt"]

    st.markdown("### Upload Reference Files")
    st.markdown(
        "Upload RIS or NBIB files exported from databases like "
        "PubMed, Scopus, Web of Science, etc."
    )

    uploaded_files = st.file_uploader(
        "Choose files",
        type=["ris", "nbib", "txt"],
        accept_multiple_files=True,
        help="Supported formats: RIS (.ris), PubMed/NBIB (.nbib, .txt)",
    )

    if uploaded_files:
        st.markdown(f"**{len(uploaded_files)} file(s) selected:**")

        for f in uploaded_files:
            # Try to detect source from filename
            source = _detect_source_from_filename(f.name)
            st.markdown(f"- {f.name} ({f.size / 1024:.1f} KB) - *{source}*")

        # Source override option
        with st.expander("Override source database"):
            for i, f in enumerate(uploaded_files):
                st.selectbox(
                    f"Source for {f.name}",
                    ["Auto-detect", "PubMed", "SCOPUS", "WOS", "EMBASE", "Cochrane", "Other"],
                    key=f"source_override_{i}",
                )

        if st.button("Process Files", type="primary"):
            on_upload(uploaded_files)


def _detect_source_from_filename(filename: str) -> str:
    """Detect database source from filename."""
    filename_lower = filename.lower()

    if "pubmed" in filename_lower or "medline" in filename_lower:
        return "PubMed"
    elif "scopus" in filename_lower:
        return "SCOPUS"
    elif "wos" in filename_lower or "web_of_science" in filename_lower:
        return "WOS"
    elif "embase" in filename_lower:
        return "EMBASE"
    elif "cochrane" in filename_lower:
        return "Cochrane"
    elif filename.endswith(".nbib"):
        return "PubMed"

    return "Unknown"


def render_export_options(
    result: DeduplicationResult,
    on_export: Callable[[str, bool], None],
) -> None:
    """
    Render export options for deduplicated results.

    Args:
        result: DeduplicationResult object
        on_export: Callback(format, include_duplicates)
    """
    st.markdown("### Export Options")

    col1, col2 = st.columns(2)

    with col1:
        export_format = st.selectbox(
            "Export Format",
            ["CSV", "RIS", "Excel"],
            key="export_format",
        )

    with col2:
        include_dups = st.checkbox(
            "Include duplicates (marked)",
            value=False,
            key="include_dups",
        )

    unique_count = result.unique_records
    total_count = result.total_records if include_dups else result.unique_records

    st.caption(f"Will export {total_count} records")

    if st.button("Export", type="primary"):
        on_export(export_format.lower(), include_dups)

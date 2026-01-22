"""Reference import component for uploading and processing database exports."""

import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Optional
from io import StringIO

from core.file_parsers import (
    RISParser,
    NBIBParser,
    BibTeXParser,
    EndNoteXMLParser,
    CSVReferenceParser,
    Deduplicator,
)
from core.storage.models import ParsedReference, DeduplicationResult


def detect_format(filename: str, content: str) -> str:
    """
    Detect file format from filename and content.

    Args:
        filename: Name of the uploaded file
        content: File content as string

    Returns:
        Detected format: "ris", "nbib", "bibtex", "endnote_xml", "csv", or "unknown"
    """
    ext = Path(filename).suffix.lower()

    # By extension
    if ext == ".bib":
        return "bibtex"
    if ext == ".nbib":
        return "nbib"
    if ext == ".ris":
        return "ris"
    if ext == ".xml":
        if EndNoteXMLParser.is_endnote_xml(content):
            return "endnote_xml"
        return "unknown_xml"
    if ext == ".csv":
        return "csv"

    # By content (for .txt or unknown extensions)
    if NBIBParser.is_nbib_format(content):
        return "nbib"
    if BibTeXParser.is_bibtex_format(content):
        return "bibtex"
    if content.strip().startswith("TY  -"):
        return "ris"
    if CSVReferenceParser.is_csv_format(content):
        return "csv"

    return "unknown"


def parse_file(filename: str, content: str, format_type: str) -> list[ParsedReference]:
    """
    Parse a file using the appropriate parser.

    Args:
        filename: Name of the file
        content: File content as string
        format_type: Detected format type

    Returns:
        List of ParsedReference objects
    """
    parsers = {
        "ris": lambda: RISParser(source_file=filename).parse(content),
        "nbib": lambda: NBIBParser(source_file=filename).parse(content),
        "bibtex": lambda: BibTeXParser(source_file=filename).parse(content),
        "endnote_xml": lambda: EndNoteXMLParser(source_file=filename).parse(content),
        "csv": lambda: CSVReferenceParser(source_file=filename).parse(content),
    }

    parser_func = parsers.get(format_type)
    if parser_func:
        return parser_func()

    return []


def parse_uploaded_files(uploaded_files: list) -> tuple[list[ParsedReference], dict[str, dict]]:
    """
    Parse all uploaded files.

    Args:
        uploaded_files: List of Streamlit uploaded file objects

    Returns:
        Tuple of (all_references, file_info_dict)
    """
    all_refs = []
    file_info = {}

    for file in uploaded_files:
        try:
            # Read file content
            content = file.getvalue().decode("utf-8", errors="ignore")

            # Detect format
            format_type = detect_format(file.name, content)

            # Parse
            refs = parse_file(file.name, content, format_type)

            # Track info
            file_info[file.name] = {
                "format": format_type,
                "count": len(refs),
                "success": True,
                "error": None,
            }

            all_refs.extend(refs)

        except Exception as e:
            file_info[file.name] = {
                "format": "unknown",
                "count": 0,
                "success": False,
                "error": str(e),
            }

    return all_refs, file_info


def render_source_summary(refs: list[ParsedReference], file_info: dict[str, dict]) -> None:
    """Render summary of parsed references by source."""
    st.subheader("Import Summary")

    # File parsing results
    for filename, info in file_info.items():
        if info["success"]:
            st.success(f"**{filename}**: {info['count']} records ({info['format']})")
        else:
            st.error(f"**{filename}**: Failed to parse - {info['error']}")

    # Count by database
    db_counts = {}
    for ref in refs:
        db = ref.source_database or "Unknown"
        db_counts[db] = db_counts.get(db, 0) + 1

    if db_counts:
        st.markdown("**Records by Database:**")
        cols = st.columns(min(len(db_counts), 4))
        for i, (db, count) in enumerate(sorted(db_counts.items(), key=lambda x: -x[1])):
            with cols[i % len(cols)]:
                st.metric(db, count)


def render_dedup_summary(result: DeduplicationResult) -> None:
    """Render deduplication summary."""
    st.subheader("Deduplication Results")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Records", result.total_records)

    with col2:
        st.metric("Unique Records", result.unique_records)

    with col3:
        st.metric("Duplicates Found", result.duplicate_count)

    with col4:
        if result.total_records > 0:
            dup_rate = (result.duplicate_count / result.total_records) * 100
            st.metric("Duplicate Rate", f"{dup_rate:.1f}%")

    # Duplicate breakdown
    if result.duplicate_count > 0:
        with st.expander("Duplicate Detection Breakdown"):
            breakdown = []
            if result.doi_duplicates > 0:
                breakdown.append(f"- DOI match: {result.doi_duplicates}")
            if result.title_fuzzy_duplicates > 0:
                breakdown.append(f"- Title similarity: {result.title_fuzzy_duplicates}")
            if result.title_author_year_duplicates > 0:
                breakdown.append(f"- Title + Author + Year: {result.title_author_year_duplicates}")

            st.markdown("\n".join(breakdown) if breakdown else "No detailed breakdown available")


def render_preview_table(
    result: DeduplicationResult,
    show_duplicates: bool = False,
) -> list[ParsedReference]:
    """
    Render preview table with record management.

    Args:
        result: DeduplicationResult with all references
        show_duplicates: Whether to show duplicate records

    Returns:
        List of references after any user modifications (removal)
    """
    st.subheader("Preview Records")

    # Get references to display
    if show_duplicates:
        refs = result.all_references
        tab_label = "All Records (including duplicates)"
    else:
        refs = [r for r in result.all_references if not r.is_duplicate]
        tab_label = "Unique Records Only"

    # Initialize removal tracking in session state
    if "removed_ref_ids" not in st.session_state:
        st.session_state.removed_ref_ids = set()

    # Filter out removed records
    display_refs = [r for r in refs if r.id not in st.session_state.removed_ref_ids]

    # Build display dataframe
    rows = []
    for ref in display_refs:
        rows.append({
            "ID": ref.id[:8],
            "Title": (ref.title[:60] + "...") if len(ref.title) > 60 else ref.title,
            "Authors": (ref.authors[:30] + "...") if ref.authors and len(ref.authors) > 30 else (ref.authors or ""),
            "Year": ref.year or "",
            "Journal": (ref.journal[:25] + "...") if ref.journal and len(ref.journal) > 25 else (ref.journal or ""),
            "Database": ref.source_database or "",
            "DOI": ref.doi[:25] + "..." if ref.doi and len(ref.doi) > 25 else (ref.doi or ""),
            "Has Abstract": "Yes" if ref.abstract else "No",
        })

    if not rows:
        st.warning("No records to display")
        return []

    df = pd.DataFrame(rows)

    # Filter options
    col1, col2 = st.columns([2, 1])

    with col1:
        search_term = st.text_input(
            "Search titles",
            key="ref_search",
            placeholder="Type to filter records...",
        )

    with col2:
        db_filter = st.multiselect(
            "Filter by database",
            options=list(set(r["Database"] for r in rows if r["Database"])),
            key="db_filter",
        )

    # Apply filters
    filtered_df = df.copy()
    if search_term:
        filtered_df = filtered_df[
            filtered_df["Title"].str.lower().str.contains(search_term.lower())
        ]
    if db_filter:
        filtered_df = filtered_df[filtered_df["Database"].isin(db_filter)]

    # Display info
    st.caption(f"Showing {len(filtered_df)} of {len(display_refs)} records")

    # Display table
    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=400,
    )

    # Batch removal options
    with st.expander("Remove Records"):
        st.markdown("**Remove individual records by ID:**")
        id_to_remove = st.text_input(
            "Enter record ID (first 8 characters)",
            key="remove_id",
            placeholder="e.g., a1b2c3d4",
        )

        if st.button("Remove Record", key="remove_btn"):
            if id_to_remove:
                # Find matching record
                for ref in refs:
                    if ref.id.startswith(id_to_remove):
                        st.session_state.removed_ref_ids.add(ref.id)
                        st.success(f"Removed record: {ref.title[:50]}...")
                        st.rerun()
                st.warning(f"No record found with ID starting with '{id_to_remove}'")

        # Reset button
        if st.button("Reset Removals", key="reset_removals"):
            st.session_state.removed_ref_ids = set()
            st.rerun()

        if st.session_state.removed_ref_ids:
            st.info(f"{len(st.session_state.removed_ref_ids)} records manually removed")

    return display_refs


def render_export_options(refs: list[ParsedReference]) -> None:
    """Render export options for the cleaned dataset."""
    st.subheader("Export Cleaned Dataset")

    col1, col2 = st.columns(2)

    with col1:
        # CSV export
        csv_data = export_to_csv(refs)
        st.download_button(
            "Download as CSV",
            csv_data,
            "cleaned_references.csv",
            "text/csv",
            key="export_csv",
        )

    with col2:
        # RIS export
        ris_data = export_to_ris(refs)
        st.download_button(
            "Download as RIS",
            ris_data,
            "cleaned_references.ris",
            "text/plain",
            key="export_ris",
        )


def export_to_csv(refs: list[ParsedReference]) -> str:
    """Export references to CSV format."""
    rows = []
    for ref in refs:
        rows.append({
            "Title": ref.title,
            "Abstract": ref.abstract or "",
            "Authors": ref.authors or "",
            "Year": ref.year or "",
            "Journal": ref.journal or "",
            "DOI": ref.doi or "",
            "PMID": ref.pmid or "",
            "Database": ref.source_database or "",
            "Source File": ref.source_file or "",
        })

    df = pd.DataFrame(rows)
    return df.to_csv(index=False)


def export_to_ris(refs: list[ParsedReference]) -> str:
    """Export references to RIS format."""
    ris_lines = []

    for ref in refs:
        ris_lines.append("TY  - JOUR")
        ris_lines.append(f"TI  - {ref.title}")

        if ref.abstract:
            ris_lines.append(f"AB  - {ref.abstract}")

        if ref.authors:
            for author in ref.authors.split(";"):
                author = author.strip()
                if author:
                    ris_lines.append(f"AU  - {author}")

        if ref.year:
            ris_lines.append(f"PY  - {ref.year}")

        if ref.journal:
            ris_lines.append(f"JO  - {ref.journal}")

        if ref.doi:
            ris_lines.append(f"DO  - {ref.doi}")

        if ref.pmid:
            ris_lines.append(f"AN  - {ref.pmid}")

        if ref.source_database:
            ris_lines.append(f"DB  - {ref.source_database}")

        ris_lines.append("ER  - ")
        ris_lines.append("")

    return "\n".join(ris_lines)


def convert_references_to_dataframe(refs: list[ParsedReference]) -> pd.DataFrame:
    """Convert ParsedReference objects to DataFrame for screening workflow."""
    rows = []
    for ref in refs:
        rows.append({
            "Title": ref.title,
            "Abstract": ref.abstract or "",
            "Authors": ref.authors or "",
            "Year": ref.year or "",
            "Journal": ref.journal or "",
            "DOI": ref.doi or "",
            "PMID": ref.pmid or "",
            "Database": ref.source_database or "",
        })

    return pd.DataFrame(rows)


def render_reference_import() -> Optional[tuple[list[ParsedReference], DeduplicationResult]]:
    """
    Render the complete reference import interface.

    Returns:
        Tuple of (unique_references, dedup_result) if ready to proceed, None otherwise
    """
    st.markdown("""
    Upload reference files exported from databases like PubMed, Scopus, Web of Science, etc.

    **Supported formats:**
    - RIS (.ris) - EndNote, Scopus, Web of Science
    - NBIB (.nbib) - PubMed/MEDLINE
    - BibTeX (.bib) - Google Scholar, Zotero, Mendeley
    - EndNote XML (.xml) - EndNote desktop
    - CSV (.csv) - Custom exports
    """)

    # Multi-file uploader
    uploaded_files = st.file_uploader(
        "Upload reference files",
        type=["ris", "nbib", "bib", "xml", "csv", "txt"],
        accept_multiple_files=True,
        help="Drag and drop multiple files from different databases",
        key="ref_import_uploader",
    )

    if not uploaded_files:
        st.info("Upload one or more reference files to begin")
        return None

    # Parse all files
    with st.spinner("Parsing files..."):
        all_refs, file_info = parse_uploaded_files(uploaded_files)

    if not all_refs:
        st.error("No records could be parsed from the uploaded files")
        return None

    # Show source summary
    render_source_summary(all_refs, file_info)

    # Large dataset warning
    if len(all_refs) > 5000:
        st.warning(
            f"Large dataset ({len(all_refs):,} records). "
            "Processing may take time and LLM screening costs will be significant."
        )

    st.divider()

    # Run deduplication
    with st.spinner("Running deduplication..."):
        deduplicator = Deduplicator(
            doi_match=True,
            fuzzy_title_match=False,  # Disabled per user preference (no fuzzy)
            title_author_year_match=True,
            fuzzy_threshold=0.85,
        )
        result = deduplicator.deduplicate(all_refs)

    # Show dedup summary
    render_dedup_summary(result)

    st.divider()

    # Preview table
    show_dups = st.checkbox("Show duplicate records", value=False, key="show_dups")
    display_refs = render_preview_table(result, show_duplicates=show_dups)

    # Get unique references (excluding removed and duplicates)
    unique_refs = [
        r for r in result.all_references
        if not r.is_duplicate and r.id not in st.session_state.get("removed_ref_ids", set())
    ]

    st.divider()

    # Export options
    render_export_options(unique_refs)

    st.divider()

    # Final count and proceed button
    st.markdown(f"### Ready to Screen: **{len(unique_refs):,}** records")

    if st.button("Proceed to Screening", type="primary", key="proceed_screening"):
        # Clear any previous screening state
        st.session_state.screening_complete = False
        st.session_state.screening_results = None
        st.session_state.studies_hash = None

        return unique_refs, result

    return None

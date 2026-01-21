"""Data Extraction page for extracting data from included studies."""

import streamlit as st
from pathlib import Path
import sys
import pandas as pd
import io

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.storage import Study, ScreeningPhase
from core.extraction import DataExtractor
from components.prisma_diagram import render_prisma_diagram
from components.progress_bar import ProgressTracker
from components.cost_display import render_cost_summary_card


def init_session_state():
    """Initialize session state variables."""
    if "extraction_results" not in st.session_state:
        st.session_state.extraction_results = None
    if "extraction_complete" not in st.session_state:
        st.session_state.extraction_complete = False


def render_sidebar():
    """Render sidebar with project info."""
    with st.sidebar:
        st.title("Data Extraction")

        if st.session_state.get("current_project"):
            project = st.session_state.current_project
            st.markdown(f"**Project:** {project.name}")

            if st.session_state.get("cost_tracker"):
                st.divider()
                render_cost_summary_card(st.session_state.cost_tracker, compact=True)
        else:
            st.warning("Please set up a project first")


def get_included_studies():
    """Get studies that passed all screening phases."""
    if not st.session_state.get("session_manager") or not st.session_state.get("current_project"):
        return []

    project = st.session_state.current_project

    # Get all studies
    all_studies = st.session_state.session_manager.get_studies(project.id)

    # Get screening decisions
    decisions = st.session_state.session_manager.get_screening_decisions(project.id)

    # Find studies that were included in final screening
    included_ids = set()
    for decision in decisions:
        if decision.decision == "included":
            included_ids.add(decision.study_id)
        elif decision.decision == "excluded":
            included_ids.discard(decision.study_id)

    # Filter studies
    included = [s for s in all_studies if s.id in included_ids]

    return included


def render_study_selection():
    """Render interface for selecting studies to extract from."""
    st.header("Studies for Extraction")

    studies = get_included_studies()

    if not studies:
        st.info("""
        No studies ready for extraction yet.

        Complete the screening process first:
        1. Title/Abstract Screening
        2. Full-text Screening (optional)
        """)
        return None

    st.success(f"Found {len(studies)} included studies")

    # Preview
    with st.expander("Preview Studies"):
        rows = []
        for study in studies:
            rows.append({
                "Title": study.title[:60] + "..." if len(study.title) > 60 else study.title,
                "PMID": study.pmid or "",
                "Has PDF Text": "✅" if study.pdf_text else "❌"
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # Check for PDF text
    studies_with_text = [s for s in studies if s.pdf_text]

    if len(studies_with_text) < len(studies):
        st.warning(
            f"⚠️ {len(studies) - len(studies_with_text)} studies don't have PDF text. "
            "Please process PDFs in Full-text Screening first."
        )

    return studies


def render_field_preview():
    """Preview configured extraction fields."""
    project = st.session_state.current_project

    if not project.extraction_fields:
        st.warning("""
        ⚠️ No extraction fields configured.

        Please configure fields in **Extraction Setup** first.
        """)
        return False

    st.header("Extraction Fields")

    fields = project.extraction_fields

    # Summary
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Fields", len(fields))

    with col2:
        required = sum(1 for f in fields if f.required)
        st.metric("Required", required)

    with col3:
        optional = len(fields) - required
        st.metric("Optional", optional)

    # Field list
    with st.expander("View Fields"):
        for field in fields:
            st.markdown(f"- **{field.field_name}** ({field.field_type.value}): {field.description}")

    return True


def run_extraction(studies):
    """Run data extraction on studies."""
    project = st.session_state.current_project

    # Filter to studies with text
    studies_with_text = [s for s in studies if s.pdf_text]

    if not studies_with_text:
        st.error("No studies have PDF text for extraction")
        return

    # Create extractor
    extractor = DataExtractor(
        llm_client=st.session_state.llm_client,
        fields=project.extraction_fields,
        cost_tracker=st.session_state.cost_tracker,
        project_id=project.id
    )

    # Estimate cost
    avg_length = sum(len(s.pdf_text or "") for s in studies_with_text) / len(studies_with_text)
    estimated_cost = extractor.estimate_cost(len(studies_with_text), int(avg_length))

    st.subheader("Cost Estimation")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Studies", len(studies_with_text))

    with col2:
        st.metric("Estimated Cost", f"${estimated_cost:.4f}")

    with col3:
        st.metric("Fields per Study", len(project.extraction_fields))

    # Budget check
    if st.session_state.cost_tracker and st.session_state.cost_tracker.budget_limit:
        if estimated_cost > st.session_state.cost_tracker.remaining_budget:
            st.error("⚠️ Estimated cost exceeds remaining budget!")
            return

    if st.button("🚀 Start Extraction", type="primary"):
        progress = ProgressTracker(len(studies_with_text), "Extracting Data")
        progress.start()

        extractions, completed = extractor.extract_batch(
            studies_with_text,
            progress_callback=progress.get_callback(),
            stop_on_budget=True
        )

        if completed:
            progress.complete()
        else:
            progress.error("Stopped due to budget limit")

        # Save extractions
        if st.session_state.session_manager:
            for extraction in extractions:
                st.session_state.session_manager.save_extraction(project.id, extraction)

            st.session_state.session_manager.save_cost_tracker(
                project.id,
                st.session_state.cost_tracker
            )

        # Get statistics
        stats = extractor.get_statistics(extractions)

        # Store results
        st.session_state.extraction_results = {
            "extractions": extractions,
            "stats": stats,
            "studies": studies_with_text,
            "dataframe": extractor.to_dataframe(extractions)
        }
        st.session_state.extraction_complete = True

        st.rerun()


def render_results():
    """Render extraction results."""
    if not st.session_state.get("extraction_results"):
        return

    results = st.session_state.extraction_results
    stats = results["stats"]
    df = results["dataframe"]

    st.header("Extraction Results")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Studies Extracted", stats["total_studies"])

    with col2:
        st.metric("Fields Extracted", stats["fields_extracted"])

    with col3:
        st.metric("Not Reported (NR)", stats["fields_not_reported"])

    with col4:
        st.metric("Completeness", f"{stats['completeness_rate']*100:.1f}%")

    # Most missing fields
    if stats["most_missing_fields"]:
        st.subheader("Fields Most Often Not Reported")
        for field_name, count in stats["most_missing_fields"]:
            st.markdown(f"- **{field_name}**: {count} studies")

    # Data table
    st.subheader("Extracted Data")

    # Highlight NR values
    st.dataframe(df, use_container_width=True)

    # Editable version
    st.subheader("Edit Extracted Data")

    st.markdown("""
    Review and edit extracted values below. Changes will be saved when you click "Save Changes".
    """)

    # Create editable dataframe (excluding _nr columns)
    edit_cols = [c for c in df.columns if not c.endswith("_nr")]
    edited_df = st.data_editor(
        df[edit_cols],
        use_container_width=True,
        num_rows="fixed"
    )

    if st.button("💾 Save Changes"):
        # TODO: Save edited values back to database
        st.success("Changes saved!")

    st.divider()

    # Export section
    render_export(df)


def render_export(df):
    """Render export options."""
    st.header("Export Data")

    col1, col2, col3 = st.columns(3)

    with col1:
        # CSV export
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            csv,
            "extracted_data.csv",
            "text/csv",
            use_container_width=True
        )

    with col2:
        # Excel export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Extracted Data')
        buffer.seek(0)

        st.download_button(
            "📥 Download Excel",
            buffer,
            "extracted_data.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col3:
        # Audit trail export
        if st.session_state.get("session_manager") and st.session_state.get("current_project"):
            from core.storage import AuditLogger

            project = st.session_state.current_project
            db_path = st.session_state.session_manager._get_db_path(project.id)
            logger = AuditLogger(db_path)

            # Export to JSON
            buffer = io.StringIO()
            import json
            entries = logger.get_entries(project_id=project.id)
            data = {
                "project_id": project.id,
                "project_name": project.name,
                "total_entries": len(entries),
                "entries": [
                    {
                        "id": e.id,
                        "operation": e.operation,
                        "study_id": e.study_id,
                        "decision": e.decision,
                        "confidence": e.confidence,
                        "cost": e.cost,
                        "timestamp": e.timestamp.isoformat()
                    }
                    for e in entries
                ]
            }
            json.dump(data, buffer, indent=2)

            st.download_button(
                "📥 Download Audit Trail",
                buffer.getvalue(),
                "audit_trail.json",
                "application/json",
                use_container_width=True
            )


def render_prisma():
    """Render final PRISMA diagram."""
    if st.session_state.get("current_project"):
        st.divider()
        render_prisma_diagram(st.session_state.current_project.prisma_counts)


def main():
    """Main function for Data Extraction page."""
    st.set_page_config(
        page_title="Data Extraction - Systematic Review App",
        page_icon="📊",
        layout="wide"
    )

    init_session_state()
    render_sidebar()

    st.title("📊 Data Extraction")

    # Check prerequisites
    if not st.session_state.get("current_project"):
        st.warning("⚠️ Please set up a project first.")
        return

    if not st.session_state.get("llm_client"):
        st.warning("⚠️ Please configure LLM in Setup first.")
        return

    # Show results if complete
    if st.session_state.extraction_complete:
        render_results()
        render_prisma()

        st.divider()
        if st.button("Start New Extraction"):
            st.session_state.extraction_complete = False
            st.session_state.extraction_results = None
            st.rerun()
        return

    # Study selection
    studies = render_study_selection()

    if studies:
        st.divider()

        # Field preview
        has_fields = render_field_preview()

        if has_fields:
            st.divider()
            run_extraction(studies)


if __name__ == "__main__":
    main()

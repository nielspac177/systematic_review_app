"""Full-text Screening page for systematic review application."""

import streamlit as st
from pathlib import Path
import sys
import pandas as pd
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.storage import Study, ScreeningPhase
from core.screening import FulltextScreener
from core.pdf import PDFProcessor, PDFBatchProcessor
from components.prisma_diagram import render_prisma_mini
from components.progress_bar import ProgressTracker
from components.cost_display import render_cost_summary_card


def init_session_state():
    """Initialize session state variables."""
    if "pdf_extractions" not in st.session_state:
        st.session_state.pdf_extractions = None
    if "fulltext_results" not in st.session_state:
        st.session_state.fulltext_results = None
    if "fulltext_complete" not in st.session_state:
        st.session_state.fulltext_complete = False


def render_sidebar():
    """Render sidebar with project info."""
    with st.sidebar:
        st.title("Full-text Screening")

        if st.session_state.get("current_project"):
            project = st.session_state.current_project
            st.markdown(f"**Project:** {project.name}")

            if st.session_state.get("cost_tracker"):
                st.divider()
                render_cost_summary_card(st.session_state.cost_tracker, compact=True)

            st.divider()
            render_prisma_mini(project.prisma_counts)
        else:
            st.warning("Please set up a project first")


def render_pdf_upload():
    """Render PDF upload interface."""
    st.header("Upload PDFs")

    st.markdown("""
    Upload PDF files for the studies that passed title/abstract screening.

    **Options:**
    - Upload individual PDFs
    - Upload a folder of PDFs (specify path)
    """)

    upload_method = st.radio(
        "Upload Method",
        options=["Upload Files", "Specify Folder Path"],
        horizontal=True
    )

    if upload_method == "Upload Files":
        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type=["pdf"],
            accept_multiple_files=True,
            help="Select all PDFs to screen"
        )

        if uploaded_files:
            st.success(f"Uploaded {len(uploaded_files)} PDF files")

            # Save uploaded files temporarily
            project = st.session_state.current_project
            if project and st.session_state.session_manager:
                project_path = st.session_state.session_manager._get_project_path(project.id)
                pdf_dir = project_path / "pdfs"
                pdf_dir.mkdir(exist_ok=True)

                saved_paths = []
                for uploaded_file in uploaded_files:
                    file_path = pdf_dir / uploaded_file.name
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved_paths.append(str(file_path))

                st.session_state.pdf_paths = saved_paths
                return True

    else:
        folder_path = st.text_input(
            "PDF Folder Path",
            help="Enter the full path to the folder containing PDFs"
        )

        if folder_path and os.path.isdir(folder_path):
            pdf_files = list(Path(folder_path).glob("*.pdf"))
            st.success(f"Found {len(pdf_files)} PDF files")

            if pdf_files:
                st.session_state.pdf_paths = [str(p) for p in pdf_files]

                with st.expander("Preview Files"):
                    for pdf in pdf_files[:10]:
                        st.markdown(f"- {pdf.name}")
                    if len(pdf_files) > 10:
                        st.markdown(f"... and {len(pdf_files) - 10} more")

                return True
        elif folder_path:
            st.error("Invalid folder path")

    return False


def run_pdf_extraction():
    """Extract text from uploaded PDFs."""
    pdf_paths = st.session_state.get("pdf_paths", [])

    if not pdf_paths:
        st.error("No PDF files available")
        return None

    st.subheader("PDF Text Extraction")

    # Extraction options
    col1, col2 = st.columns(2)

    with col1:
        use_ocr = st.checkbox(
            "Enable OCR fallback",
            value=True,
            help="Use OCR for PDFs where direct text extraction fails"
        )

    with col2:
        dpi = st.slider(
            "OCR DPI",
            min_value=100,
            max_value=300,
            value=200,
            help="Higher DPI = better OCR quality but slower"
        ) if use_ocr else 200

    if st.button("Extract Text from PDFs", type="primary"):
        processor = PDFProcessor(ocr_enabled=use_ocr, dpi=dpi)

        progress = ProgressTracker(len(pdf_paths), "Extracting PDF Text")
        progress.start()

        results = []
        for i, pdf_path in enumerate(pdf_paths):
            progress.update(i, f"Processing: {Path(pdf_path).name}")
            result = processor.extract_text(pdf_path)
            results.append({
                "path": pdf_path,
                "filename": Path(pdf_path).name,
                "result": result
            })

        progress.complete()

        st.session_state.pdf_extractions = results

        # Show summary
        summary = processor.get_extraction_summary([r["result"] for r in results])

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Successful", summary["successful"])

        with col2:
            st.metric("Failed", summary["failed"])

        with col3:
            st.metric("Avg Words", f"{summary['average_words']:.0f}")

        return results

    return None


def render_extraction_results():
    """Display PDF extraction results."""
    if not st.session_state.get("pdf_extractions"):
        return

    results = st.session_state.pdf_extractions

    st.subheader("Extraction Results")

    # Create table
    rows = []
    for r in results:
        rows.append({
            "Filename": r["filename"],
            "Status": "✅ Success" if r["result"].success else "❌ Failed",
            "Method": r["result"].method,
            "Words": r["result"].word_count,
            "Pages": r["result"].page_count,
            "Error": r["result"].error or ""
        })

    df = pd.DataFrame(rows)

    # Filter tabs
    tab1, tab2 = st.tabs(["All", "Failed Only"])

    with tab1:
        st.dataframe(df, use_container_width=True)

    with tab2:
        failed_df = df[df["Status"] == "❌ Failed"]
        if len(failed_df) > 0:
            st.dataframe(failed_df, use_container_width=True)
        else:
            st.success("No failed extractions!")


def run_fulltext_screening():
    """Run full-text screening on extracted PDFs."""
    project = st.session_state.current_project
    extractions = st.session_state.pdf_extractions

    if not extractions:
        st.error("Please extract PDF text first")
        return

    # Create Study objects with PDF text
    studies = []
    for ext in extractions:
        if ext["result"].success:
            study = Study(
                title=ext["filename"].replace(".pdf", ""),
                pdf_path=ext["path"],
                pdf_text=ext["result"].text,
            )
            studies.append(study)

    if not studies:
        st.error("No successful extractions to screen")
        return

    # Estimate cost
    screener = FulltextScreener(
        llm_client=st.session_state.llm_client,
        criteria=project.criteria,
        research_question=project.research_question,
        cost_tracker=st.session_state.cost_tracker,
        project_id=project.id,
    )

    avg_length = sum(len(s.pdf_text or "") for s in studies) / len(studies)
    estimated_cost = screener.estimate_cost(len(studies), int(avg_length))

    st.subheader("Cost Estimation")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Studies to Screen", len(studies))

    with col2:
        st.metric("Estimated Cost", f"${estimated_cost:.4f}")

    with col3:
        st.metric("Avg Text Length", f"{avg_length/1000:.1f}K chars")

    # Budget check
    if st.session_state.cost_tracker and st.session_state.cost_tracker.budget_limit:
        if estimated_cost > st.session_state.cost_tracker.remaining_budget:
            st.error("⚠️ Estimated cost exceeds remaining budget!")
            return

    if st.button("🚀 Start Full-text Screening", type="primary"):
        progress = ProgressTracker(len(studies), "Full-text Screening")
        progress.start()

        decisions, completed = screener.screen_batch(
            studies,
            progress_callback=progress.get_callback(),
            stop_on_budget=True
        )

        if completed:
            progress.complete()
        else:
            progress.error("Stopped due to budget limit")

        # Save decisions
        if st.session_state.session_manager:
            for decision in decisions:
                st.session_state.session_manager.save_screening_decision(project.id, decision)

            st.session_state.session_manager.save_cost_tracker(
                project.id,
                st.session_state.cost_tracker
            )

        # Update PRISMA counts
        stats = screener.get_statistics(decisions)

        project.prisma_counts.reports_assessed = len(studies)
        project.prisma_counts.reports_excluded = stats["excluded"]
        project.prisma_counts.studies_included = stats["included"]

        # Save project
        if st.session_state.session_manager:
            st.session_state.session_manager.save_project(project)

        # Store results
        st.session_state.fulltext_results = {
            "decisions": decisions,
            "stats": stats,
            "studies": studies,
            "completed": completed
        }
        st.session_state.fulltext_complete = True

        st.rerun()


def render_results():
    """Render full-text screening results."""
    if not st.session_state.get("fulltext_results"):
        return

    results = st.session_state.fulltext_results
    stats = results["stats"]
    decisions = results["decisions"]
    studies = results["studies"]

    st.header("Full-text Screening Results")

    # Summary metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Assessed", stats["total"])

    with col2:
        st.metric("Included", stats["included"])

    with col3:
        st.metric("Excluded", stats["excluded"])

    # Not accessible count
    if stats["not_accessible"] > 0:
        st.warning(f"⚠️ {stats['not_accessible']} studies could not be assessed (text not accessible)")

    # Exclusion reasons
    st.subheader("Exclusion Reasons")

    if stats["exclusion_by_category"]:
        reasons_df = pd.DataFrame([
            {"Reason": k.replace("_", " ").title(), "Count": v}
            for k, v in stats["exclusion_by_category"].items()
        ])
        st.bar_chart(reasons_df.set_index("Reason"))

    # Results table
    st.subheader("Detailed Results")

    rows = []
    study_map = {s.id: s for s in studies}

    for decision in decisions:
        study = study_map.get(decision.study_id)
        if study:
            rows.append({
                "Study": study.title[:60] + "..." if len(study.title) > 60 else study.title,
                "Decision": decision.decision.title(),
                "Reason": decision.reason[:100] + "..." if len(decision.reason) > 100 else decision.reason,
                "Category": decision.reason_category.value.replace("_", " ").title(),
                "Confidence": f"{decision.confidence:.2f}",
            })

    results_df = pd.DataFrame(rows)

    tab1, tab2, tab3 = st.tabs(["All", "Included", "Excluded"])

    with tab1:
        st.dataframe(results_df, use_container_width=True)

    with tab2:
        included_df = results_df[results_df["Decision"] == "Included"]
        st.dataframe(included_df, use_container_width=True)

    with tab3:
        excluded_df = results_df[results_df["Decision"] == "Excluded"]
        st.dataframe(excluded_df, use_container_width=True)

    # Export
    st.subheader("Export")

    col1, col2 = st.columns(2)

    with col1:
        csv = results_df.to_csv(index=False)
        st.download_button(
            "📥 Download Results (CSV)",
            csv,
            "fulltext_screening_results.csv",
            "text/csv"
        )

    with col2:
        included_df = results_df[results_df["Decision"] == "Included"]
        csv = included_df.to_csv(index=False)
        st.download_button(
            "📥 Download Included Only (CSV)",
            csv,
            "included_fulltext.csv",
            "text/csv"
        )


def main():
    """Main function for Full-text Screening page."""
    st.set_page_config(
        page_title="Full-text Screening - Systematic Review App",
        page_icon="📄",
        layout="wide"
    )

    init_session_state()
    render_sidebar()

    st.title("📄 Full-text Screening")

    # Check prerequisites
    if not st.session_state.get("current_project"):
        st.warning("⚠️ Please set up a project first in the Setup page.")
        return

    if not st.session_state.get("llm_client"):
        st.warning("⚠️ Please configure LLM settings in the Setup page.")
        return

    # Show results if complete
    if st.session_state.fulltext_complete:
        render_results()

        st.divider()
        if st.button("Start New Full-text Screening"):
            st.session_state.fulltext_complete = False
            st.session_state.fulltext_results = None
            st.session_state.pdf_extractions = None
            st.rerun()

        st.success("""
        ✅ **Full-text Screening Complete!**

        Proceed to **Data Extraction** to extract data from included studies.
        """)
        return

    # PDF upload
    has_pdfs = render_pdf_upload()

    if has_pdfs:
        st.divider()

        # PDF extraction
        if not st.session_state.get("pdf_extractions"):
            run_pdf_extraction()

        # Show extraction results
        render_extraction_results()

        # Run screening
        if st.session_state.get("pdf_extractions"):
            st.divider()
            run_fulltext_screening()


if __name__ == "__main__":
    main()

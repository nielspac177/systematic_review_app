"""Title and Abstract Screening page for systematic review application.

This module includes protections against duplicate API calls from Streamlit reruns:
- Session state caching for screening results
- Screening lock to prevent concurrent operations
- Screener instance persistence with built-in decision cache
"""

import streamlit as st
from pathlib import Path
import sys
import pandas as pd
import io
import hashlib
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm import CostTracker, OperationType
from core.storage import SessionManager, Study, ScreeningPhase
from core.screening import TitleAbstractScreener
from components.prisma_diagram import render_prisma_mini, update_prisma_counts
from components.progress_bar import ProgressTracker
from components.cost_display import render_cost_estimate, render_cost_confirmation, render_cost_summary_card
from components.reference_import import render_reference_import, convert_references_to_dataframe

# Configure logging
logger = logging.getLogger(__name__)


def get_studies_hash(df: pd.DataFrame, mapping: dict) -> str:
    """
    Generate a hash of the uploaded studies for cache validation.

    This helps detect when the user has uploaded new data that requires
    re-screening, versus a simple page rerun.

    Args:
        df: Studies DataFrame
        mapping: Column mapping dictionary

    Returns:
        Hash string
    """
    # Create a fingerprint of the data
    content = f"{len(df)}|{df.columns.tolist()}|{mapping}"
    if len(df) > 0:
        # Include first and last titles for uniqueness
        first_title = str(df.iloc[0][mapping.get("title", "Title")])[:100]
        last_title = str(df.iloc[-1][mapping.get("title", "Title")])[:100]
        content += f"|{first_title}|{last_title}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def init_session_state():
    """Initialize session state variables."""
    if "uploaded_studies" not in st.session_state:
        st.session_state.uploaded_studies = None
    if "screening_results" not in st.session_state:
        st.session_state.screening_results = None
    if "screening_complete" not in st.session_state:
        st.session_state.screening_complete = False

    # Rate limiting protection: track screening state
    if "screening_in_progress" not in st.session_state:
        st.session_state.screening_in_progress = False
    if "screener_instance" not in st.session_state:
        st.session_state.screener_instance = None
    if "studies_hash" not in st.session_state:
        st.session_state.studies_hash = None
    if "screened_study_ids" not in st.session_state:
        st.session_state.screened_study_ids = set()

    # Reference import tracking
    if "import_sources" not in st.session_state:
        st.session_state.import_sources = None
    if "import_dedup_count" not in st.session_state:
        st.session_state.import_dedup_count = None
    if "removed_ref_ids" not in st.session_state:
        st.session_state.removed_ref_ids = set()


def render_sidebar():
    """Render sidebar with project info."""
    with st.sidebar:
        st.title("Title/Abstract Screening")

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


def render_file_upload():
    """Render file upload interface."""
    st.header("Upload Studies")

    st.markdown("""
    Upload a CSV file containing your studies. The file should have at minimum:
    - A **Title** column
    - An **Abstract** column

    Optional columns: PMID, DOI, Authors, Year, Journal
    """)

    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=["csv"],
        help="Upload your exported search results"
    )

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            st.session_state.uploaded_studies = df

            st.success(f"Loaded {len(df)} studies")

            # Preview
            with st.expander("Preview Data"):
                st.dataframe(df.head(10))

            # Column mapping
            st.subheader("Column Mapping")

            col1, col2 = st.columns(2)

            with col1:
                title_col = st.selectbox(
                    "Title Column",
                    options=df.columns.tolist(),
                    index=df.columns.tolist().index("Title") if "Title" in df.columns else 0
                )

            with col2:
                abstract_col = st.selectbox(
                    "Abstract Column",
                    options=df.columns.tolist(),
                    index=df.columns.tolist().index("Abstract") if "Abstract" in df.columns else 0
                )

            # Optional columns
            with st.expander("Optional Columns"):
                col1, col2 = st.columns(2)

                with col1:
                    pmid_col = st.selectbox(
                        "PMID Column",
                        options=["None"] + df.columns.tolist(),
                        index=df.columns.tolist().index("PMID") + 1 if "PMID" in df.columns else 0
                    )

                with col2:
                    doi_col = st.selectbox(
                        "DOI Column",
                        options=["None"] + df.columns.tolist(),
                        index=df.columns.tolist().index("DOI") + 1 if "DOI" in df.columns else 0
                    )

            # Store column mappings
            st.session_state.column_mapping = {
                "title": title_col,
                "abstract": abstract_col,
                "pmid": pmid_col if pmid_col != "None" else None,
                "doi": doi_col if doi_col != "None" else None
            }

            return True

        except Exception as e:
            st.error(f"Error loading file: {e}")
            return False

    return False


def render_cost_estimation():
    """Render cost estimation before screening."""
    if not st.session_state.get("uploaded_studies") is not None:
        return False

    if not st.session_state.get("llm_client"):
        st.warning("Please configure LLM in Setup first")
        return False

    if not st.session_state.get("current_project") or not st.session_state.current_project.criteria:
        st.warning("Please generate criteria in Setup first")
        return False

    df = st.session_state.uploaded_studies
    n_studies = len(df)

    st.header("Cost Estimation")

    # Use cached screener for estimation (prevents creating duplicate instances)
    screener = get_or_create_screener()

    # Account for already-cached decisions
    cached_count = screener.get_cached_count()
    studies_to_screen = max(0, n_studies - cached_count)

    estimated_cost = screener.estimate_cost(studies_to_screen)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Studies to Screen", f"{studies_to_screen:,}")
        if cached_count > 0:
            st.caption(f"({cached_count} already cached)")

    with col2:
        st.metric("Estimated Cost", f"${estimated_cost:.4f}")

    with col3:
        if st.session_state.cost_tracker and st.session_state.cost_tracker.budget_limit:
            remaining = st.session_state.cost_tracker.remaining_budget
            st.metric("Remaining Budget", f"${remaining:.4f}")

    # Show cached studies info
    if cached_count > 0:
        st.info(f"ℹ️ {cached_count} studies have cached decisions and will not require API calls.")

    # Budget check
    if st.session_state.cost_tracker and st.session_state.cost_tracker.budget_limit:
        if estimated_cost > st.session_state.cost_tracker.remaining_budget:
            st.error("⚠️ Estimated cost exceeds remaining budget!")
            return False

    return True


def get_or_create_screener():
    """
    Get or create the screener instance with caching.

    The screener maintains an internal decision cache that persists
    across Streamlit reruns, preventing duplicate API calls.
    """
    project = st.session_state.current_project

    # Check if we need to create a new screener
    # (new project, new criteria, or no screener yet)
    current_criteria_hash = hashlib.sha256(
        str(project.criteria).encode()
    ).hexdigest()[:8] if project.criteria else None

    need_new_screener = (
        st.session_state.screener_instance is None or
        st.session_state.get("screener_project_id") != project.id or
        st.session_state.get("screener_criteria_hash") != current_criteria_hash
    )

    if need_new_screener:
        logger.info(f"Creating new screener instance for project {project.id}")
        st.session_state.screener_instance = TitleAbstractScreener(
            llm_client=st.session_state.llm_client,
            criteria=project.criteria,
            research_question=project.research_question,
            cost_tracker=st.session_state.cost_tracker,
            project_id=project.id,
        )
        st.session_state.screener_project_id = project.id
        st.session_state.screener_criteria_hash = current_criteria_hash
        # Reset screened study IDs when screener changes
        st.session_state.screened_study_ids = set()

    return st.session_state.screener_instance


def run_screening():
    """
    Run the title/abstract screening process.

    This function includes multiple protections against duplicate API calls:
    1. Screening lock prevents concurrent execution on Streamlit reruns
    2. Study hash validation detects when data has changed
    3. Screener's internal cache skips already-processed studies
    """
    # PROTECTION 1: Check if screening is already in progress
    if st.session_state.screening_in_progress:
        logger.warning("Screening already in progress, ignoring duplicate request")
        st.warning("Screening is already running. Please wait...")
        return None, None

    # Set the lock IMMEDIATELY before any processing
    st.session_state.screening_in_progress = True

    try:
        project = st.session_state.current_project
        df = st.session_state.uploaded_studies
        mapping = st.session_state.column_mapping

        # PROTECTION 2: Check if this data was already screened
        current_hash = get_studies_hash(df, mapping)
        if (st.session_state.studies_hash == current_hash and
            st.session_state.screening_results is not None):
            logger.info("Studies already screened (hash match), returning cached results")
            st.session_state.screening_in_progress = False
            return (
                st.session_state.screening_results["decisions"],
                st.session_state.screening_results["stats"]
            )

        # Convert DataFrame to Study objects
        studies = []
        for idx, row in df.iterrows():
            study = Study(
                title=str(row[mapping["title"]]),
                abstract=str(row[mapping["abstract"]]) if pd.notna(row[mapping["abstract"]]) else None,
                pmid=str(row[mapping["pmid"]]) if mapping["pmid"] and pd.notna(row.get(mapping["pmid"])) else None,
                doi=str(row[mapping["doi"]]) if mapping["doi"] and pd.notna(row.get(mapping["doi"])) else None,
            )
            studies.append(study)

        # Add studies to project
        if st.session_state.session_manager:
            st.session_state.session_manager.add_studies(project.id, studies)

        # PROTECTION 3: Get screener with persistent cache
        screener = get_or_create_screener()

        # Log cache status
        cached_count = screener.get_cached_count()
        if cached_count > 0:
            logger.info(f"Screener has {cached_count} cached decisions")

        # Progress tracking
        progress = ProgressTracker(len(studies), "Screening Studies")
        progress.start()

        # Run screening (screener internally skips cached studies)
        decisions, completed = screener.screen_batch(
            studies,
            progress_callback=progress.get_callback(),
            stop_on_budget=True,
            skip_cached=True  # Use screener's internal cache
        )

        if completed:
            progress.complete()
        else:
            progress.error("Stopped due to budget limit")

        # Save decisions
        if st.session_state.session_manager:
            for decision in decisions:
                st.session_state.session_manager.save_screening_decision(project.id, decision)
                # Track screened study IDs
                st.session_state.screened_study_ids.add(decision.study_id)

            # Save cost tracker
            st.session_state.session_manager.save_cost_tracker(
                project.id,
                st.session_state.cost_tracker
            )

        # Update PRISMA counts
        stats = screener.get_statistics(decisions)

        project.prisma_counts.records_identified_databases = len(studies)
        project.prisma_counts.records_screened = len(studies)
        project.prisma_counts.records_excluded_screening = stats["excluded"]
        project.prisma_counts.reports_sought = stats["included"]

        # Track duplicates removed if from import
        if st.session_state.get("import_dedup_count"):
            project.prisma_counts.records_removed_duplicates = st.session_state.import_dedup_count

        # Update exclusion reasons
        for reason, count in stats["exclusion_by_category"].items():
            project.prisma_counts.exclusion_reasons[f"screening_{reason}"] = count

        # Store source database tracking for PRISMA reporting
        if st.session_state.get("import_sources"):
            # Store records per database in exclusion_reasons dict for now
            # (PRISMACounts model could be extended to have a dedicated field)
            for db, count in st.session_state.import_sources.items():
                project.prisma_counts.exclusion_reasons[f"source_{db}"] = count

        # Save project
        if st.session_state.session_manager:
            st.session_state.session_manager.save_project(project)

        # Store results for display AND cache validation
        st.session_state.screening_results = {
            "decisions": decisions,
            "stats": stats,
            "studies": studies,
            "completed": completed
        }
        st.session_state.screening_complete = True
        st.session_state.studies_hash = current_hash  # Mark this data as screened

        return decisions, stats

    except Exception as e:
        logger.error(f"Screening failed with error: {e}")
        st.error(f"Screening error: {e}")
        raise
    finally:
        # ALWAYS release the lock
        st.session_state.screening_in_progress = False


def render_results():
    """Render screening results."""
    if not st.session_state.get("screening_results"):
        return

    results = st.session_state.screening_results
    stats = results["stats"]
    decisions = results["decisions"]
    studies = results["studies"]

    st.header("Screening Results")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Screened", stats["total"])

    with col2:
        st.metric("Included", stats["included"], delta=None)

    with col3:
        st.metric("Excluded", stats["excluded"], delta=None)

    with col4:
        st.metric(
            "Inclusion Rate",
            f"{stats['inclusion_rate']*100:.1f}%"
        )

    # Low confidence alert
    if stats["low_confidence_count"] > 0:
        st.warning(
            f"⚠️ {stats['low_confidence_count']} studies have low confidence scores "
            f"(< 0.8) and will be flagged for re-review."
        )

    # Exclusion reasons breakdown
    st.subheader("Exclusion Reasons")

    if stats["exclusion_by_category"]:
        reasons_df = pd.DataFrame([
            {"Reason": k.replace("_", " ").title(), "Count": v}
            for k, v in stats["exclusion_by_category"].items()
        ])
        st.bar_chart(reasons_df.set_index("Reason"))

    # Results table
    st.subheader("Detailed Results")

    # Build results dataframe
    rows = []
    study_map = {s.id: s for s in studies}

    for decision in decisions:
        study = study_map.get(decision.study_id)
        if study:
            rows.append({
                "Title": study.title[:80] + "..." if len(study.title) > 80 else study.title,
                "Decision": decision.decision.title(),
                "Reason": decision.reason[:50] + "..." if len(decision.reason) > 50 else decision.reason,
                "Category": decision.reason_category.value.replace("_", " ").title(),
                "Confidence": f"{decision.confidence:.2f}",
                "PMID": study.pmid or "",
            })

    results_df = pd.DataFrame(rows)

    # Filter tabs
    tab1, tab2, tab3 = st.tabs(["All", "Included", "Excluded"])

    with tab1:
        st.dataframe(results_df, use_container_width=True)

    with tab2:
        included_df = results_df[results_df["Decision"] == "Included"]
        st.dataframe(included_df, use_container_width=True)

    with tab3:
        excluded_df = results_df[results_df["Decision"] == "Excluded"]
        st.dataframe(excluded_df, use_container_width=True)

    # Export buttons
    st.subheader("Export Results")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Export included
        included_df = results_df[results_df["Decision"] == "Included"]
        csv = included_df.to_csv(index=False)
        st.download_button(
            "📥 Download Included (CSV)",
            csv,
            "included_studies.csv",
            "text/csv"
        )

    with col2:
        # Export excluded
        excluded_df = results_df[results_df["Decision"] == "Excluded"]
        csv = excluded_df.to_csv(index=False)
        st.download_button(
            "📥 Download Excluded (CSV)",
            csv,
            "excluded_studies.csv",
            "text/csv"
        )

    with col3:
        # Export all
        csv = results_df.to_csv(index=False)
        st.download_button(
            "📥 Download All (CSV)",
            csv,
            "all_screening_results.csv",
            "text/csv"
        )


def main():
    """Main function for Title/Abstract Screening page."""
    st.set_page_config(
        page_title="Title/Abstract Screening - Systematic Review App",
        page_icon="📑",
        layout="wide"
    )

    init_session_state()
    render_sidebar()

    st.title("📑 Title/Abstract Screening")

    # Check prerequisites
    if not st.session_state.get("current_project"):
        st.warning("⚠️ Please set up a project first in the Setup page.")
        st.page_link("pages/0_Setup_Review.py", label="Go to Setup", icon="📋")
        return

    if not st.session_state.current_project.criteria:
        st.warning("⚠️ Please generate criteria first in the Setup page.")
        st.page_link("pages/0_Setup_Review.py", label="Go to Setup", icon="📋")
        return

    if not st.session_state.get("llm_client"):
        st.warning("⚠️ Please configure LLM settings in the Setup page.")
        st.page_link("pages/0_Setup_Review.py", label="Go to Setup", icon="📋")
        return

    # Show results if screening is complete
    if st.session_state.screening_complete:
        render_results()

        st.divider()
        if st.button("Start New Screening"):
            # Clear all screening-related state and caches
            st.session_state.screening_complete = False
            st.session_state.screening_results = None
            st.session_state.uploaded_studies = None
            st.session_state.studies_hash = None
            st.session_state.screened_study_ids = set()
            st.session_state.removed_ref_ids = set()
            st.session_state.import_sources = None
            # Clear the screener's decision cache
            if st.session_state.screener_instance:
                cleared = st.session_state.screener_instance.clear_cache()
                logger.info(f"Cleared {cleared} cached decisions")
            st.session_state.screener_instance = None
            st.rerun()

        st.success("""
        ✅ **Screening Complete!**

        Next steps:
        - Review the **Feedback Review** page for low-confidence decisions
        - Or proceed to **Full-text Screening** with included studies
        """)
        return

    # Two tabs: existing CSV upload + new reference import
    tab1, tab2 = st.tabs(["Upload CSV", "Import from Database Export"])

    has_data = False

    with tab1:
        # Existing CSV upload logic
        has_data = render_file_upload()

    with tab2:
        # New reference import from database exports
        import_result = render_reference_import()
        if import_result:
            unique_refs, dedup_result = import_result

            # Convert to DataFrame for existing workflow
            df = convert_references_to_dataframe(unique_refs)
            st.session_state.uploaded_studies = df
            st.session_state.column_mapping = {
                "title": "Title",
                "abstract": "Abstract",
                "pmid": "PMID",
                "doi": "DOI"
            }
            # Store source tracking for PRISMA reporting
            st.session_state.import_sources = dedup_result.records_per_source
            st.session_state.import_dedup_count = dedup_result.duplicate_count
            has_data = True

    if has_data:
        st.divider()

        # Cost estimation
        can_proceed = render_cost_estimation()

        if can_proceed:
            st.divider()

            # Start screening button
            if st.button("🚀 Start Screening", type="primary", use_container_width=True):
                with st.spinner("Running screening..."):
                    run_screening()
                    st.rerun()


if __name__ == "__main__":
    main()

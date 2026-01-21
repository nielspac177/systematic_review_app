"""Feedback Review page for re-reviewing low-confidence exclusions."""

import streamlit as st
from pathlib import Path
import sys
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.storage import ScreeningPhase
from core.screening import FeedbackReviewer
from components.prisma_diagram import render_prisma_mini
from components.progress_bar import ProgressTracker
from components.cost_display import render_cost_summary_card


def init_session_state():
    """Initialize session state variables."""
    if "feedback_decisions" not in st.session_state:
        st.session_state.feedback_decisions = None
    if "feedback_complete" not in st.session_state:
        st.session_state.feedback_complete = False
    if "user_overrides" not in st.session_state:
        st.session_state.user_overrides = {}


def render_sidebar():
    """Render sidebar with project info."""
    with st.sidebar:
        st.title("Feedback Review")

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


def load_low_confidence_decisions():
    """Load decisions that need re-review."""
    if not st.session_state.get("session_manager") or not st.session_state.get("current_project"):
        return []

    project = st.session_state.current_project

    # Get low confidence exclusions
    decisions = st.session_state.session_manager.get_low_confidence_exclusions(
        project.id,
        threshold=0.8
    )

    return decisions


def render_flagged_studies():
    """Render list of studies flagged for review."""
    decisions = load_low_confidence_decisions()

    if not decisions:
        st.info("No studies flagged for review. All exclusion decisions have high confidence.")
        return None

    st.header(f"Studies Flagged for Review ({len(decisions)})")

    st.markdown("""
    These studies were excluded with **low confidence** (< 0.8).
    The AI will re-evaluate each decision with an inclusive mindset.
    You can then review and override any decisions.
    """)

    # Get study details
    studies = {}
    for decision in decisions:
        study = st.session_state.session_manager.get_study(
            st.session_state.current_project.id,
            decision.study_id
        )
        if study:
            studies[decision.study_id] = study

    # Display table
    rows = []
    for decision in decisions:
        study = studies.get(decision.study_id)
        if study:
            rows.append({
                "Study ID": decision.study_id[:8] + "...",
                "Title": study.title[:60] + "..." if len(study.title) > 60 else study.title,
                "Original Reason": decision.reason[:40] + "..." if len(decision.reason) > 40 else decision.reason,
                "Confidence": f"{decision.confidence:.2f}",
                "Phase": decision.phase.value.replace("_", " ").title()
            })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    return decisions, studies


def run_feedback_review(decisions, studies):
    """Run the feedback review process."""
    project = st.session_state.current_project

    reviewer = FeedbackReviewer(
        llm_client=st.session_state.llm_client,
        criteria=project.criteria,
        research_question=project.research_question,
        cost_tracker=st.session_state.cost_tracker,
        project_id=project.id,
    )

    # Estimate cost
    estimated_cost = reviewer.estimate_cost(len(decisions))

    st.subheader("Cost Estimation")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Studies to Review", len(decisions))

    with col2:
        st.metric("Estimated Cost", f"${estimated_cost:.4f}")

    # Budget check
    if st.session_state.cost_tracker and st.session_state.cost_tracker.budget_limit:
        if estimated_cost > st.session_state.cost_tracker.remaining_budget:
            st.error("⚠️ Estimated cost exceeds remaining budget!")
            return

    if st.button("🔄 Run AI Re-Review", type="primary"):
        progress = ProgressTracker(len(decisions), "Re-reviewing Decisions")
        progress.start()

        updated_decisions, completed = reviewer.review_batch(
            decisions,
            studies,
            progress_callback=progress.get_callback(),
            stop_on_budget=True
        )

        if completed:
            progress.complete()
        else:
            progress.error("Stopped due to budget limit")

        # Save updated decisions
        if st.session_state.session_manager:
            for decision in updated_decisions:
                st.session_state.session_manager.save_screening_decision(
                    project.id, decision
                )

            st.session_state.session_manager.save_cost_tracker(
                project.id,
                st.session_state.cost_tracker
            )

        st.session_state.feedback_decisions = updated_decisions
        st.session_state.feedback_studies = studies
        st.session_state.feedback_complete = True

        st.rerun()


def render_review_interface():
    """Render interface for user review of AI recommendations."""
    if not st.session_state.get("feedback_decisions"):
        return

    decisions = st.session_state.feedback_decisions
    studies = st.session_state.feedback_studies

    st.header("Review AI Recommendations")

    # Summary
    reconsidered = [d for d in decisions if d.feedback_reconsider]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Reviewed", len(decisions))

    with col2:
        st.metric("AI Recommends Include", len(reconsidered))

    with col3:
        st.metric("AI Maintains Exclude", len(decisions) - len(reconsidered))

    st.divider()

    # Individual review cards
    for i, decision in enumerate(decisions):
        study = studies.get(decision.study_id)
        if not study:
            continue

        with st.expander(
            f"{'🟡' if decision.feedback_reconsider else '🔴'} {study.title[:60]}...",
            expanded=i < 5  # Expand first 5
        ):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Title:** {study.title}")
                if study.abstract:
                    st.markdown(f"**Abstract:** {study.abstract[:300]}...")

                st.markdown(f"**Original Exclusion Reason:** {decision.reason}")
                st.markdown(f"**Original Confidence:** {decision.confidence:.2f}")

            with col2:
                st.markdown("### AI Recommendation")

                if decision.feedback_reconsider:
                    st.success("🟢 **RECONSIDER FOR INCLUSION**")
                else:
                    st.error("🔴 **MAINTAIN EXCLUSION**")

                st.markdown(f"**Rationale:** {decision.feedback_rationale}")
                st.markdown(f"**New Confidence:** {decision.feedback_new_confidence:.2f}")

            # User override
            st.markdown("### Your Decision")

            current_override = st.session_state.user_overrides.get(decision.study_id)

            override = st.radio(
                "Final Decision",
                options=["Accept AI Recommendation", "Override: Include", "Override: Exclude"],
                index=0 if not current_override else (
                    1 if current_override == "included" else 2
                ),
                key=f"override_{decision.study_id}",
                horizontal=True
            )

            if override == "Override: Include":
                st.session_state.user_overrides[decision.study_id] = "included"
            elif override == "Override: Exclude":
                st.session_state.user_overrides[decision.study_id] = "excluded"
            elif decision.study_id in st.session_state.user_overrides:
                del st.session_state.user_overrides[decision.study_id]

    st.divider()

    # Apply overrides
    if st.button("💾 Save All Decisions", type="primary"):
        save_final_decisions(decisions)


def save_final_decisions(decisions):
    """Save final decisions after user review."""
    project = st.session_state.current_project

    # Apply user overrides
    for decision in decisions:
        if decision.study_id in st.session_state.user_overrides:
            decision.feedback_final_decision = st.session_state.user_overrides[decision.study_id]

        # Save to database
        st.session_state.session_manager.save_screening_decision(
            project.id, decision
        )

    # Update PRISMA counts
    final_included = sum(
        1 for d in decisions
        if d.feedback_final_decision == "included"
    )

    # Add to reports sought (for full-text screening)
    project.prisma_counts.reports_sought += final_included

    st.session_state.session_manager.save_project(project)

    st.success(f"""
    ✅ **Decisions Saved!**

    - {final_included} studies will be added to full-text screening
    - {len(decisions) - final_included} studies remain excluded
    """)


def render_summary():
    """Render final summary."""
    if not st.session_state.get("feedback_decisions"):
        return

    decisions = st.session_state.feedback_decisions

    st.header("Summary")

    # Calculate final counts
    final_included = sum(
        1 for d in decisions
        if (d.study_id in st.session_state.user_overrides and
            st.session_state.user_overrides[d.study_id] == "included") or
           (d.study_id not in st.session_state.user_overrides and d.feedback_reconsider)
    )

    final_excluded = len(decisions) - final_included

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Reviewed", len(decisions))

    with col2:
        st.metric("Final Included", final_included)

    with col3:
        st.metric("Final Excluded", final_excluded)


def main():
    """Main function for Feedback Review page."""
    st.set_page_config(
        page_title="Feedback Review - Systematic Review App",
        page_icon="🔄",
        layout="wide"
    )

    init_session_state()
    render_sidebar()

    st.title("🔄 Feedback Review")

    st.markdown("""
    This page allows you to review screening decisions that had **low confidence scores**.
    The AI will re-evaluate these decisions with an inclusive mindset, and you can
    override any recommendations.
    """)

    # Check prerequisites
    if not st.session_state.get("current_project"):
        st.warning("⚠️ Please set up a project first.")
        return

    if not st.session_state.get("llm_client"):
        st.warning("⚠️ Please configure LLM settings in Setup.")
        return

    # Show review interface if already run
    if st.session_state.feedback_complete:
        render_review_interface()
        render_summary()

        st.divider()
        if st.button("Start New Review"):
            st.session_state.feedback_complete = False
            st.session_state.feedback_decisions = None
            st.session_state.user_overrides = {}
            st.rerun()
        return

    # Load and display flagged studies
    result = render_flagged_studies()

    if result:
        decisions, studies = result
        st.divider()
        run_feedback_review(decisions, studies)


if __name__ == "__main__":
    main()

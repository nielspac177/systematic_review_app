"""Risk of Bias Assessment page for conducting RoB evaluations."""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.storage.models import RoBToolType, JudgmentLevel, StudyRoBAssessment
from core.risk_of_bias.template_manager import RoBTemplateManager
from core.risk_of_bias.assessor import RoBAssessor
from core.risk_of_bias.study_design_detector import StudyDesignDetector
from components.cost_display import render_cost_summary_card
from components.traffic_light_plot import (
    render_traffic_light_plot, render_judgment_legend,
    render_distribution_chart, render_rob_summary_metrics
)
from components.rob_judgment_form import render_domain_judgment_form
from components.rob_summary_table import (
    render_rob_summary_table, render_flagged_items,
    render_verification_progress, render_export_options
)
from components.progress_bar import ProgressTracker


def init_session_state():
    """Initialize session state variables."""
    if "rob_current_study_idx" not in st.session_state:
        st.session_state.rob_current_study_idx = 0
    if "rob_assessments_cache" not in st.session_state:
        st.session_state.rob_assessments_cache = {}
    if "rob_assessment_in_progress" not in st.session_state:
        st.session_state.rob_assessment_in_progress = False
    if "rob_view_mode" not in st.session_state:
        st.session_state.rob_view_mode = "single"


def render_sidebar():
    """Render sidebar with project info and navigation."""
    with st.sidebar:
        st.title("Risk of Bias")

        if st.session_state.get("current_project"):
            project = st.session_state.current_project
            st.markdown(f"**Project:** {project.name}")

            if st.session_state.get("cost_tracker"):
                st.divider()
                render_cost_summary_card(st.session_state.cost_tracker, compact=True)

            st.divider()

            # View mode selector
            st.markdown("**View Mode**")
            view_mode = st.radio(
                "Select view",
                options=["single", "batch", "summary"],
                format_func=lambda x: {"single": "Single Study", "batch": "Batch Assessment", "summary": "Summary View"}[x],
                key="rob_view_mode_selector",
                label_visibility="collapsed",
            )
            st.session_state.rob_view_mode = view_mode
        else:
            st.warning("Please set up a project first")


def get_included_studies():
    """Get studies that passed screening."""
    if not st.session_state.get("session_manager") or not st.session_state.get("current_project"):
        return []

    project = st.session_state.current_project
    all_studies = st.session_state.session_manager.get_studies(project.id)
    decisions = st.session_state.session_manager.get_screening_decisions(project.id)

    included_ids = set()
    for decision in decisions:
        if decision.decision == "included":
            included_ids.add(decision.study_id)
        elif decision.decision == "excluded":
            included_ids.discard(decision.study_id)

    return [s for s in all_studies if s.id in included_ids]


def get_assessments():
    """Get all RoB assessments for current project."""
    if not st.session_state.get("session_manager") or not st.session_state.get("current_project"):
        return []

    return st.session_state.session_manager.get_rob_assessments(
        st.session_state.current_project.id
    )


def get_settings():
    """Get RoB settings for current project."""
    if not st.session_state.get("session_manager") or not st.session_state.get("current_project"):
        return None

    return st.session_state.session_manager.get_rob_settings(
        st.session_state.current_project.id
    )


def render_single_study_view():
    """Render single study assessment interface."""
    st.header("Single Study Assessment")

    studies = get_included_studies()
    if not studies:
        st.info("No included studies found. Complete screening first.")
        return

    settings = get_settings()
    if not settings or not settings.enabled_tools:
        st.warning("Please configure RoB tools in RoB Setup first.")
        return

    # Study navigation
    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        if st.button("Previous", disabled=st.session_state.rob_current_study_idx == 0):
            st.session_state.rob_current_study_idx -= 1
            st.rerun()

    with col2:
        study_options = [f"{s.title[:50]}..." if len(s.title) > 50 else s.title for s in studies]
        selected_idx = st.selectbox(
            "Select Study",
            range(len(studies)),
            index=st.session_state.rob_current_study_idx,
            format_func=lambda i: f"{i+1}. {study_options[i]}",
            label_visibility="collapsed",
        )
        if selected_idx != st.session_state.rob_current_study_idx:
            st.session_state.rob_current_study_idx = selected_idx
            st.rerun()

    with col3:
        if st.button("Next", disabled=st.session_state.rob_current_study_idx >= len(studies) - 1):
            st.session_state.rob_current_study_idx += 1
            st.rerun()

    st.caption(f"Study {st.session_state.rob_current_study_idx + 1} of {len(studies)}")

    current_study = studies[st.session_state.rob_current_study_idx]

    # Study info
    with st.expander("Study Details", expanded=False):
        st.markdown(f"**Title:** {current_study.title}")
        st.markdown(f"**Authors:** {current_study.authors or 'Unknown'}")
        st.markdown(f"**Year:** {current_study.year or 'Unknown'}")
        if current_study.abstract:
            st.markdown("**Abstract:**")
            st.markdown(current_study.abstract[:1000] + "..." if len(current_study.abstract or "") > 1000 else current_study.abstract)

    # Check for existing assessment
    existing_assessment = st.session_state.session_manager.get_rob_assessment(
        st.session_state.current_project.id,
        current_study.id
    )

    # Tool selection
    tool_options = [(t, RoBTemplateManager.TOOL_DISPLAY_NAMES.get(t, t.value)) for t in settings.enabled_tools]
    selected_tool_name = st.selectbox(
        "Assessment Tool",
        [name for _, name in tool_options],
    )
    selected_tool = tool_options[[name for _, name in tool_options].index(selected_tool_name)][0]

    # Get template
    template_manager = RoBTemplateManager(
        session_manager=st.session_state.session_manager,
        project_id=st.session_state.current_project.id
    )
    template = template_manager.get_template(selected_tool)

    if not template:
        st.error("Template not found")
        return

    # Assessment actions
    col1, col2 = st.columns(2)

    with col1:
        if existing_assessment:
            st.success(f"Assessment exists: {existing_assessment.overall_judgment.value}")

    with col2:
        if st.button("Run AI Assessment", type="primary", disabled=st.session_state.rob_assessment_in_progress):
            run_single_assessment(current_study, template)

    # Display/edit assessment
    if existing_assessment:
        render_assessment_form(template, existing_assessment, current_study)


def run_single_assessment(study, template):
    """Run AI assessment for a single study."""
    st.session_state.rob_assessment_in_progress = True

    try:
        # Cost estimate
        assessor = RoBAssessor(
            llm_client=st.session_state.llm_client,
            template=template,
            cost_tracker=st.session_state.cost_tracker,
            session_manager=st.session_state.session_manager,
            project_id=st.session_state.current_project.id,
        )

        text_length = len(study.pdf_text or study.abstract or "")
        estimated_cost = assessor.estimate_cost(1, text_length)

        with st.spinner(f"Running assessment (est. ${estimated_cost:.4f})..."):
            assessment = assessor.assess_study(study, skip_cached=False)

        st.success("Assessment complete!")
        st.session_state.rob_assessments_cache[study.id] = assessment

        # Save cost tracker
        if st.session_state.get("session_manager"):
            st.session_state.session_manager.save_cost_tracker(
                st.session_state.current_project.id,
                st.session_state.cost_tracker
            )

        st.rerun()

    except Exception as e:
        st.error(f"Assessment failed: {str(e)}")
    finally:
        st.session_state.rob_assessment_in_progress = False


def render_assessment_form(template, assessment, study):
    """Render the assessment form for editing."""
    st.subheader("Assessment Details")

    # Domain tabs
    domain_names = [d.short_name for d in sorted(template.domains, key=lambda x: x.display_order)]

    tabs = st.tabs(domain_names + ["Overall"])

    domain_map = {d.id: d for d in template.domains}
    judgment_map = {dj.domain_id: dj for dj in assessment.domain_judgments}

    for i, domain in enumerate(sorted(template.domains, key=lambda x: x.display_order)):
        with tabs[i]:
            dj = judgment_map.get(domain.id)

            updated_judgment = render_domain_judgment_form(
                domain,
                existing_judgment=dj,
                key_prefix=f"edit_{study.id}",
                editable=True,
                show_ai_suggestion=True,
            )

            if st.button(f"Save {domain.short_name}", key=f"save_{domain.id}"):
                # Update judgment
                for j, judgment in enumerate(assessment.domain_judgments):
                    if judgment.domain_id == domain.id:
                        assessment.domain_judgments[j] = updated_judgment
                        break

                st.session_state.session_manager.save_rob_assessment(
                    st.session_state.current_project.id,
                    assessment
                )
                st.success("Saved!")

    # Overall tab
    with tabs[-1]:
        st.subheader("Overall Judgment")

        from core.risk_of_bias.visualization import JUDGMENT_COLORS, JUDGMENT_LABELS

        color = JUDGMENT_COLORS.get(assessment.overall_judgment, "#808080")
        label = JUDGMENT_LABELS.get(assessment.overall_judgment, "Unknown")

        st.markdown(
            f'<h2 style="background-color: {color}; padding: 16px; border-radius: 8px; text-align: center;">'
            f'{label}</h2>',
            unsafe_allow_html=True
        )

        st.markdown("**Rationale:**")
        st.markdown(assessment.overall_rationale or "No rationale provided")

        st.markdown("---")

        # Domain summary
        st.markdown("**Domain Summary:**")
        for dj in assessment.domain_judgments:
            d_color = JUDGMENT_COLORS.get(dj.judgment, "#808080")
            d_label = JUDGMENT_LABELS.get(dj.judgment, "Unknown")
            verified = "(Verified)" if dj.is_human_verified else ""
            flagged = "(Review)" if dj.is_flagged_uncertain else ""
            st.markdown(
                f'<span style="background-color: {d_color}; padding: 2px 8px; border-radius: 4px; margin-right: 8px;">'
                f'{dj.domain_name}: {d_label}</span> {verified} {flagged}',
                unsafe_allow_html=True
            )


def render_batch_view():
    """Render batch assessment interface."""
    st.header("Batch Assessment")

    studies = get_included_studies()
    if not studies:
        st.info("No included studies found.")
        return

    settings = get_settings()
    if not settings or not settings.enabled_tools:
        st.warning("Please configure RoB tools first.")
        return

    # Get existing assessments
    assessments = get_assessments()
    assessed_ids = {a.study_id for a in assessments}
    unassessed = [s for s in studies if s.id not in assessed_ids]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Studies", len(studies))
    with col2:
        st.metric("Assessed", len(assessed_ids))
    with col3:
        st.metric("Remaining", len(unassessed))

    if not unassessed:
        st.success("All studies have been assessed!")
        return

    # Tool selection
    tool_options = [(t, RoBTemplateManager.TOOL_DISPLAY_NAMES.get(t, t.value)) for t in settings.enabled_tools]
    selected_tool_name = st.selectbox(
        "Assessment Tool for Batch",
        [name for _, name in tool_options],
    )
    selected_tool = tool_options[[name for _, name in tool_options].index(selected_tool_name)][0]

    # Get template
    template_manager = RoBTemplateManager(
        session_manager=st.session_state.session_manager,
        project_id=st.session_state.current_project.id
    )
    template = template_manager.get_template(selected_tool)

    # Cost estimate
    assessor = RoBAssessor(
        llm_client=st.session_state.llm_client,
        template=template,
        cost_tracker=st.session_state.cost_tracker,
        session_manager=st.session_state.session_manager,
        project_id=st.session_state.current_project.id,
    )

    avg_length = sum(len(s.pdf_text or s.abstract or "") for s in unassessed) / len(unassessed) if unassessed else 5000
    estimated_cost = assessor.estimate_cost(len(unassessed), int(avg_length))

    st.info(f"Estimated cost for {len(unassessed)} studies: **${estimated_cost:.4f}**")

    # Budget check
    if st.session_state.cost_tracker and st.session_state.cost_tracker.budget_limit:
        remaining = st.session_state.cost_tracker.remaining_budget
        if estimated_cost > remaining:
            st.warning(f"Estimated cost exceeds remaining budget (${remaining:.4f})")

    if st.button("Start Batch Assessment", type="primary", disabled=st.session_state.rob_assessment_in_progress):
        run_batch_assessment(unassessed, assessor)


def run_batch_assessment(studies, assessor):
    """Run batch assessment."""
    st.session_state.rob_assessment_in_progress = True

    try:
        progress = ProgressTracker(len(studies), "Assessing Studies")
        progress.start()

        results, completed = assessor.assess_batch(
            studies,
            progress_callback=progress.get_callback(),
            stop_on_budget=True,
        )

        if completed:
            progress.complete()
            st.success(f"Completed {len(results)} assessments")
        else:
            progress.error("Stopped due to budget limit")
            st.warning(f"Completed {len(results)} of {len(studies)} assessments")

        # Save cost tracker
        if st.session_state.get("session_manager"):
            st.session_state.session_manager.save_cost_tracker(
                st.session_state.current_project.id,
                st.session_state.cost_tracker
            )

        st.rerun()

    except Exception as e:
        st.error(f"Batch assessment failed: {str(e)}")
    finally:
        st.session_state.rob_assessment_in_progress = False


def render_summary_view():
    """Render summary visualization view."""
    st.header("Assessment Summary")

    studies = get_included_studies()
    assessments = get_assessments()

    if not assessments:
        st.info("No assessments yet. Run single or batch assessments first.")
        return

    # Summary metrics
    render_rob_summary_metrics(assessments)

    st.divider()

    # Verification progress
    st.subheader("Verification Progress")
    render_verification_progress(assessments)

    st.divider()

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["Traffic Light Plot", "Distribution", "Flagged Items", "Export"])

    with tab1:
        st.subheader("Risk of Bias Traffic Light Plot")
        render_judgment_legend()
        render_traffic_light_plot(assessments, studies)

    with tab2:
        st.subheader("Judgment Distribution")

        chart_type = st.radio("Chart type", ["bar", "pie"], horizontal=True)
        render_distribution_chart(assessments, chart_type)

    with tab3:
        st.subheader("Items Requiring Review")

        def on_review_click(study_id, domain_id):
            # Navigate to single study view
            for i, s in enumerate(studies):
                if s.id == study_id:
                    st.session_state.rob_current_study_idx = i
                    st.session_state.rob_view_mode = "single"
                    st.rerun()

        render_flagged_items(assessments, studies, on_review_click)

    with tab4:
        render_export_options(assessments, studies)


def main():
    """Main function for Risk of Bias page."""
    st.set_page_config(
        page_title="Risk of Bias - Systematic Review App",
        page_icon="⚖️",
        layout="wide"
    )

    init_session_state()
    render_sidebar()

    st.title("⚖️ Risk of Bias Assessment")

    # Check prerequisites
    if not st.session_state.get("current_project"):
        st.warning("Please set up a project first.")
        return

    if not st.session_state.get("llm_client"):
        st.warning("Please configure LLM in Setup first.")
        return

    # Render based on view mode
    view_mode = st.session_state.rob_view_mode

    if view_mode == "single":
        render_single_study_view()
    elif view_mode == "batch":
        render_batch_view()
    else:
        render_summary_view()


if __name__ == "__main__":
    main()

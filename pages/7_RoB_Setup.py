"""Risk of Bias Setup page for configuring RoB assessment tools."""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.storage.models import RoBToolType, RoBProjectSettings
from core.risk_of_bias.template_manager import RoBTemplateManager
from core.risk_of_bias.study_design_detector import StudyDesignDetector
from components.cost_display import render_cost_summary_card


def init_session_state():
    """Initialize session state variables."""
    if "rob_settings" not in st.session_state:
        st.session_state.rob_settings = None
    if "rob_template_manager" not in st.session_state:
        st.session_state.rob_template_manager = None
    if "rob_design_analysis" not in st.session_state:
        st.session_state.rob_design_analysis = None


def render_sidebar():
    """Render sidebar with project info."""
    with st.sidebar:
        st.title("RoB Setup")

        if st.session_state.get("current_project"):
            project = st.session_state.current_project
            st.markdown(f"**Project:** {project.name}")

            if st.session_state.get("cost_tracker"):
                st.divider()
                render_cost_summary_card(st.session_state.cost_tracker, compact=True)
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


def render_tool_selection():
    """Render tool selection interface."""
    st.header("Select Assessment Tools")

    st.markdown("""
    Choose the Risk of Bias assessment tools appropriate for your study types.
    The system can auto-detect study designs or you can manually select tools.
    """)

    # Initialize template manager
    if not st.session_state.rob_template_manager:
        st.session_state.rob_template_manager = RoBTemplateManager(
            session_manager=st.session_state.get("session_manager"),
            project_id=st.session_state.current_project.id if st.session_state.get("current_project") else None
        )

    template_manager = st.session_state.rob_template_manager

    # Get available templates
    templates = template_manager.list_available_templates()

    # Auto-detect option
    st.subheader("Auto-Detect Study Designs")

    studies = get_included_studies()

    if studies:
        st.info(f"Found {len(studies)} included studies")

        if st.button("Analyze Study Designs"):
            with st.spinner("Analyzing study designs..."):
                detector = StudyDesignDetector(
                    llm_client=st.session_state.get("llm_client"),
                    cost_tracker=st.session_state.get("cost_tracker"),
                )

                def progress_callback(current, total):
                    st.progress(current / total, f"Analyzing {current}/{total}")

                analysis = detector.suggest_tools_for_project(studies, progress_callback)
                st.session_state.rob_design_analysis = analysis

        # Display analysis results
        if st.session_state.rob_design_analysis:
            analysis = st.session_state.rob_design_analysis

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Study Design Distribution:**")
                for design, count in analysis["design_distribution"].items():
                    st.markdown(f"- {design}: {count}")

            with col2:
                st.markdown("**Recommended Tools:**")
                for tool, count in analysis["tool_recommendations"].items():
                    st.markdown(f"- {tool}: {count} studies")

            if analysis["mixed_designs"]:
                st.warning("Your studies have mixed designs. Consider using multiple assessment tools.")

            st.markdown(f"**Suggested Primary Tool:** {analysis['suggested_primary_tool']}")
    else:
        st.info("No included studies found. Complete screening first.")

    st.divider()

    # Manual tool selection
    st.subheader("Manual Tool Selection")

    # Load existing settings
    settings = None
    if st.session_state.get("session_manager") and st.session_state.get("current_project"):
        settings = st.session_state.session_manager.get_rob_settings(
            st.session_state.current_project.id
        )

    enabled_tools = settings.enabled_tools if settings else []

    # Group templates by category
    categories = {
        "Randomized Trials": [RoBToolType.ROB_2, RoBToolType.JBI_RCT],
        "Non-Randomized Studies": [RoBToolType.ROBINS_I, RoBToolType.NEWCASTLE_OTTAWA_COHORT,
                                   RoBToolType.NEWCASTLE_OTTAWA_CASE_CONTROL, RoBToolType.NEWCASTLE_OTTAWA_CROSS_SECTIONAL,
                                   RoBToolType.JBI_COHORT],
        "Diagnostic Studies": [RoBToolType.QUADAS_2],
        "Qualitative Studies": [RoBToolType.JBI_QUALITATIVE],
    }

    selected_tools = []

    for category, tool_types in categories.items():
        st.markdown(f"**{category}**")

        for tool_type in tool_types:
            template_info = next((t for t in templates if t["tool_type"] == tool_type), None)
            if template_info:
                checked = tool_type in enabled_tools
                if st.checkbox(
                    template_info["display_name"],
                    value=checked,
                    key=f"tool_{tool_type.value}",
                    help=template_info["description"][:200] + "..."
                ):
                    selected_tools.append(tool_type)

    # Save settings
    if st.button("Save Tool Selection", type="primary"):
        project = st.session_state.current_project

        if settings:
            settings.enabled_tools = selected_tools
        else:
            settings = RoBProjectSettings(
                project_id=project.id,
                enabled_tools=selected_tools,
            )

        st.session_state.session_manager.save_rob_settings(project.id, settings)
        st.session_state.rob_settings = settings
        st.success(f"Saved {len(selected_tools)} tool(s)")


def render_tool_configuration():
    """Render tool configuration options."""
    st.header("Configuration Options")

    # Load settings
    settings = None
    if st.session_state.get("session_manager") and st.session_state.get("current_project"):
        settings = st.session_state.session_manager.get_rob_settings(
            st.session_state.current_project.id
        )

    if not settings:
        st.info("Please select tools first")
        return

    col1, col2 = st.columns(2)

    with col1:
        auto_detect = st.checkbox(
            "Auto-detect study designs",
            value=settings.auto_detect_study_design,
            help="Automatically suggest appropriate RoB tool based on study design"
        )

        require_quotes = st.checkbox(
            "Require supporting quotes",
            value=settings.require_supporting_quotes,
            help="Require verbatim quotes from text for each judgment"
        )

    with col2:
        dual_review = st.checkbox(
            "Enable dual review",
            value=settings.dual_review_enabled,
            help="Require two independent reviewers for each assessment"
        )

        threshold = st.slider(
            "Flag uncertain threshold",
            min_value=0.0,
            max_value=1.0,
            value=settings.flag_uncertain_threshold,
            help="Flag AI assessments below this confidence for human review"
        )

    if st.button("Save Configuration"):
        settings.auto_detect_study_design = auto_detect
        settings.require_supporting_quotes = require_quotes
        settings.dual_review_enabled = dual_review
        settings.flag_uncertain_threshold = threshold

        st.session_state.session_manager.save_rob_settings(
            st.session_state.current_project.id, settings
        )
        st.success("Configuration saved")


def render_template_preview():
    """Render template preview and customization."""
    st.header("Template Preview")

    template_manager = st.session_state.rob_template_manager

    if not template_manager:
        return

    # Get enabled tools
    settings = None
    if st.session_state.get("session_manager") and st.session_state.get("current_project"):
        settings = st.session_state.session_manager.get_rob_settings(
            st.session_state.current_project.id
        )

    enabled_tools = settings.enabled_tools if settings else []

    if not enabled_tools:
        st.info("Please select tools to preview their templates")
        return

    # Tool selector
    tool_options = [template_manager.TOOL_DISPLAY_NAMES.get(t, t.value) for t in enabled_tools]
    selected_tool_name = st.selectbox("Select tool to preview", tool_options)

    selected_tool = enabled_tools[tool_options.index(selected_tool_name)]

    # Get template
    template = template_manager.get_template(selected_tool)

    if template:
        st.markdown(f"**{template.name}** (v{template.version})")
        st.caption(template.description)

        st.markdown(f"**Applicable study designs:** {', '.join(template.applicable_study_designs)}")

        # Show domains
        st.subheader("Domains")

        for domain in sorted(template.domains, key=lambda d: d.display_order):
            with st.expander(f"{domain.short_name}: {domain.name}"):
                st.markdown(domain.description)

                st.markdown("**Signaling Questions:**")
                for i, sq in enumerate(domain.signaling_questions, 1):
                    st.markdown(f"{i}. {sq.question_text}")
                    if sq.guidance:
                        st.caption(f"   Guidance: {sq.guidance}")

                if domain.judgment_guidance:
                    st.markdown("**Judgment Guidance:**")
                    for level, guidance in domain.judgment_guidance.items():
                        st.markdown(f"- **{level}**: {guidance}")

        # Customization option
        st.divider()
        st.subheader("Customization")
        st.info("Template customization coming soon. You can modify domain names, add/remove signaling questions, and adjust judgment criteria.")


def main():
    """Main function for RoB Setup page."""
    st.set_page_config(
        page_title="Risk of Bias Setup - Systematic Review App",
        page_icon="⚖️",
        layout="wide"
    )

    init_session_state()
    render_sidebar()

    st.title("⚖️ Risk of Bias Setup")

    # Check prerequisites
    if not st.session_state.get("current_project"):
        st.warning("Please set up a project first.")
        return

    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs(["Tool Selection", "Configuration", "Template Preview"])

    with tab1:
        render_tool_selection()

    with tab2:
        render_tool_configuration()

    with tab3:
        render_template_preview()


if __name__ == "__main__":
    main()

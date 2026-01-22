"""Setup Review page for systematic review application."""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm import get_llm_client, CostTracker
from core.storage import SessionManager, Project, ReviewType
from core.screening import CriteriaGenerator
from components.cost_display import render_budget_input, render_cost_summary_card


def init_session_state():
    """Initialize session state variables."""
    if "session_manager" not in st.session_state:
        st.session_state.session_manager = None
    if "current_project" not in st.session_state:
        st.session_state.current_project = None
    if "cost_tracker" not in st.session_state:
        st.session_state.cost_tracker = None
    if "llm_client" not in st.session_state:
        st.session_state.llm_client = None
    if "criteria_generated" not in st.session_state:
        st.session_state.criteria_generated = False


def render_project_selection():
    """Render project selection or creation interface."""
    st.header("Project Setup")

    # Storage folder selection
    default_path = str(Path.home() / "systematic_reviews")
    storage_path = st.text_input(
        "Storage Folder",
        value=default_path,
        help="Folder where project data will be saved"
    )

    # Initialize session manager
    if storage_path:
        try:
            st.session_state.session_manager = SessionManager(storage_path)
        except Exception as e:
            st.error(f"Error accessing storage folder: {e}")
            return

    # Option to load existing or create new
    tab1, tab2 = st.tabs(["New Project", "Load Existing"])

    with tab1:
        render_new_project_form()

    with tab2:
        render_existing_projects()


def render_new_project_form():
    """Render form for creating new project."""
    st.subheader("Create New Project")

    with st.form("new_project_form"):
        project_name = st.text_input(
            "Project Name",
            placeholder="e.g., Depression Treatment Meta-Analysis"
        )

        research_question = st.text_area(
            "Research Question",
            placeholder="e.g., What is the effectiveness of cognitive behavioral therapy compared to pharmacotherapy for treating major depressive disorder in adults?",
            height=100
        )

        review_type = st.selectbox(
            "Review Type",
            options=["standard", "rapid", "scoping"],
            format_func=lambda x: {
                "standard": "Standard Systematic Review (PRISMA 2020)",
                "rapid": "Rapid Review",
                "scoping": "Scoping Review"
            }.get(x, x)
        )

        submitted = st.form_submit_button("Create Project", type="primary")

        if submitted:
            if not project_name or not research_question:
                st.error("Please fill in all required fields")
            elif st.session_state.session_manager:
                try:
                    project = st.session_state.session_manager.create_project(
                        name=project_name,
                        research_question=research_question,
                        review_type=review_type
                    )
                    st.session_state.current_project = project
                    st.session_state.cost_tracker = CostTracker()
                    st.success(f"Project '{project_name}' created!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating project: {e}")


def render_existing_projects():
    """Render list of existing projects."""
    st.subheader("Load Existing Project")

    if not st.session_state.session_manager:
        st.info("Set storage folder first")
        return

    projects = st.session_state.session_manager.list_projects()

    if not projects:
        st.info("No existing projects found")
        return

    for project in projects:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.markdown(f"**{project['name']}**")
                st.caption(f"Created: {project['created_at'][:10]}")

            with col2:
                if st.button("Load", key=f"load_{project['id']}"):
                    loaded = st.session_state.session_manager.load_project(project['id'])
                    if loaded:
                        st.session_state.current_project = loaded
                        st.session_state.cost_tracker = st.session_state.session_manager.load_cost_tracker(project['id'])
                        st.success(f"Loaded '{loaded.name}'")
                        st.rerun()

            with col3:
                if st.button("Delete", key=f"delete_{project['id']}", type="secondary"):
                    if st.session_state.session_manager.delete_project(project['id']):
                        st.success("Project deleted")
                        st.rerun()

            st.divider()


def render_llm_configuration():
    """Render LLM provider and model configuration."""
    st.header("LLM Configuration")

    col1, col2 = st.columns(2)

    with col1:
        provider = st.selectbox(
            "LLM Provider",
            options=["openai", "anthropic"],
            format_func=lambda x: "OpenAI (GPT-5/GPT-4)" if x == "openai" else "Anthropic (Claude)"
        )

    with col2:
        if provider == "openai":
            model = st.selectbox(
                "Model",
                options=[
                    "gpt-5.2-pro",
                    "gpt-5.2",
                    "gpt-5",
                    "gpt-5-mini",
                    "gpt-5-nano",
                    "gpt-4.1",
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4-turbo",
                    "gpt-3.5-turbo",
                ],
                index=6,  # Default to gpt-4o
                format_func=lambda x: {
                    "gpt-5.2-pro": "GPT-5.2 Pro (Most capable)",
                    "gpt-5.2": "GPT-5.2",
                    "gpt-5": "GPT-5",
                    "gpt-5-mini": "GPT-5 Mini (Fast & affordable)",
                    "gpt-5-nano": "GPT-5 Nano (Fastest & cheapest)",
                    "gpt-4.1": "GPT-4.1",
                    "gpt-4o": "GPT-4o",
                    "gpt-4o-mini": "GPT-4o Mini",
                    "gpt-4-turbo": "GPT-4 Turbo",
                    "gpt-3.5-turbo": "GPT-3.5 Turbo",
                }.get(x, x)
            )
        else:
            model = st.selectbox(
                "Model",
                options=[
                    "claude-sonnet-4-20250514",
                    "claude-opus-4-20250514",
                    "claude-3-7-sonnet-latest",
                    "claude-3-5-sonnet-latest",
                    "claude-3-5-haiku-latest",
                    "claude-3-opus-latest",
                    "claude-3-haiku-20240307",
                ],
                format_func=lambda x: {
                    "claude-sonnet-4-20250514": "Claude Sonnet 4 (Recommended)",
                    "claude-opus-4-20250514": "Claude Opus 4 (Most capable)",
                    "claude-3-7-sonnet-latest": "Claude 3.7 Sonnet",
                    "claude-3-5-sonnet-latest": "Claude 3.5 Sonnet",
                    "claude-3-5-haiku-latest": "Claude 3.5 Haiku (Fast)",
                    "claude-3-opus-latest": "Claude 3 Opus",
                    "claude-3-haiku-20240307": "Claude 3 Haiku (Cheapest)",
                }.get(x, x)
            )

    # API Key input
    api_key = st.text_input(
        f"{provider.title()} API Key",
        type="password",
        help="Your API key will not be stored"
    )

    # Budget settings
    budget_limit = render_budget_input(
        current_limit=st.session_state.current_project.budget_limit if st.session_state.current_project else None
    )

    if api_key:
        try:
            client = get_llm_client(provider, api_key, model)
            st.session_state.llm_client = client

            # Update project
            if st.session_state.current_project:
                st.session_state.current_project.llm_provider = provider
                st.session_state.current_project.llm_model = model
                st.session_state.current_project.budget_limit = budget_limit

                if st.session_state.cost_tracker:
                    st.session_state.cost_tracker.budget_limit = budget_limit

            st.success(f"✅ Connected to {provider.title()} ({model})")
        except Exception as e:
            st.error(f"Error connecting to LLM: {e}")


def render_criteria_generation():
    """Render criteria generation interface."""
    st.header("Inclusion/Exclusion Criteria")

    if not st.session_state.llm_client:
        st.warning("Please configure LLM settings first")
        return

    project = st.session_state.current_project
    if not project:
        st.warning("Please create or load a project first")
        return

    # Show existing criteria if available
    if project.criteria:
        st.subheader("Current Criteria")
        render_criteria_display(project.criteria)

        if st.button("Regenerate Criteria"):
            st.session_state.criteria_generated = False
            st.rerun()
    else:
        st.info("Click the button below to generate criteria using AI")

        if st.button("Generate Criteria with AI", type="primary"):
            with st.spinner("Generating criteria..."):
                try:
                    generator = CriteriaGenerator(
                        llm_client=st.session_state.llm_client,
                        cost_tracker=st.session_state.cost_tracker,
                        project_id=project.id
                    )

                    criteria = generator.generate_criteria(project.research_question)
                    project.criteria = criteria
                    st.session_state.criteria_generated = True

                    # Save project
                    if st.session_state.session_manager:
                        st.session_state.session_manager.save_project(project)

                    st.success("Criteria generated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating criteria: {e}")


def render_criteria_display(criteria):
    """Display and allow editing of criteria."""
    st.subheader("Inclusion Criteria (PICO)")

    with st.form("criteria_form"):
        population = st.text_area(
            "Population",
            value=criteria.inclusion.population,
            height=80
        )

        intervention = st.text_area(
            "Intervention/Exposure",
            value=criteria.inclusion.intervention,
            height=80
        )

        comparison = st.text_area(
            "Comparison",
            value=criteria.inclusion.comparison,
            height=80
        )

        outcome = st.text_area(
            "Outcome",
            value=criteria.inclusion.outcome,
            height=80
        )

        study_design = st.text_area(
            "Study Design",
            value=criteria.inclusion.study_design,
            height=80
        )

        st.subheader("Exclusion Criteria")
        exclusion_text = st.text_area(
            "Exclusion criteria (one per line)",
            value="\n".join(criteria.exclusion),
            height=120
        )

        submitted = st.form_submit_button("Save Criteria", type="primary")

        if submitted:
            # Update criteria
            from core.storage.models import InclusionCriteria, ReviewCriteria

            new_inclusion = InclusionCriteria(
                population=population,
                intervention=intervention,
                comparison=comparison,
                outcome=outcome,
                study_design=study_design
            )

            new_exclusion = [line.strip() for line in exclusion_text.split("\n") if line.strip()]

            st.session_state.current_project.criteria = ReviewCriteria(
                inclusion=new_inclusion,
                exclusion=new_exclusion,
                suggested_exclusion_reasons=criteria.suggested_exclusion_reasons
            )

            if st.session_state.session_manager:
                st.session_state.session_manager.save_project(st.session_state.current_project)

            st.success("Criteria saved!")


def render_sidebar():
    """Render sidebar with project info and navigation."""
    with st.sidebar:
        st.title("Systematic Review")

        if st.session_state.current_project:
            st.markdown(f"**Project:** {st.session_state.current_project.name}")
            st.markdown(f"**Type:** {st.session_state.current_project.review_type}")

            if st.session_state.cost_tracker:
                st.divider()
                render_cost_summary_card(st.session_state.cost_tracker, compact=True)

            st.divider()

            # Navigation hints
            st.markdown("**Next Steps:**")
            if not st.session_state.current_project.criteria:
                st.markdown("1. ⏳ Generate criteria")
            else:
                st.markdown("1. ✅ Criteria set")
                st.markdown("2. → Go to Title/Abstract Screening")
        else:
            st.info("Create or load a project to begin")


def main():
    """Main function for Setup page."""
    st.set_page_config(
        page_title="Setup Review - Systematic Review App",
        page_icon="📋",
        layout="wide"
    )

    init_session_state()
    render_sidebar()

    st.title("📋 Setup Systematic Review")

    # Project selection/creation
    render_project_selection()

    # Only show remaining sections if project is loaded
    if st.session_state.current_project:
        st.divider()
        render_llm_configuration()

        st.divider()
        render_criteria_generation()

        # Ready to proceed message
        if (st.session_state.current_project.criteria and
            st.session_state.llm_client):
            st.divider()
            st.success("""
            ✅ **Setup Complete!**

            You're ready to begin screening. Navigate to **Title/Abstract Screening**
            in the sidebar to upload your studies and start the screening process.
            """)


if __name__ == "__main__":
    main()

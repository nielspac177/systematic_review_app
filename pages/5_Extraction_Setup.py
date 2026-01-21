"""Extraction Setup page for configuring data extraction fields."""

import streamlit as st
from pathlib import Path
import sys
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.storage import ExtractionField, FieldType
from core.extraction import FieldRecommender, DEFAULT_FIELDS
from components.cost_display import render_cost_summary_card


def init_session_state():
    """Initialize session state variables."""
    if "extraction_fields" not in st.session_state:
        st.session_state.extraction_fields = None
    if "fields_configured" not in st.session_state:
        st.session_state.fields_configured = False


def render_sidebar():
    """Render sidebar with project info."""
    with st.sidebar:
        st.title("Extraction Setup")

        if st.session_state.get("current_project"):
            project = st.session_state.current_project
            st.markdown(f"**Project:** {project.name}")

            if st.session_state.get("cost_tracker"):
                st.divider()
                render_cost_summary_card(st.session_state.cost_tracker, compact=True)
        else:
            st.warning("Please set up a project first")


def render_field_recommendation():
    """Render AI field recommendation interface."""
    st.header("Field Recommendation")

    st.markdown("""
    The AI can recommend extraction fields based on your research question.
    You can also use default fields or add custom ones.
    """)

    project = st.session_state.current_project

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🤖 Get AI Recommendations", type="primary"):
            if st.session_state.get("llm_client"):
                with st.spinner("Generating recommendations..."):
                    recommender = FieldRecommender(
                        llm_client=st.session_state.llm_client,
                        cost_tracker=st.session_state.cost_tracker,
                        project_id=project.id
                    )

                    fields = recommender.recommend_fields(
                        project.research_question,
                        study_types=["RCT", "Cohort"]  # Could be configurable
                    )

                    st.session_state.extraction_fields = fields
                    st.success(f"Generated {len(fields)} recommended fields")
                    st.rerun()
            else:
                st.error("Please configure LLM in Setup first")

    with col2:
        if st.button("📋 Use Default Fields"):
            default_fields = []
            for category_fields in DEFAULT_FIELDS.values():
                default_fields.extend(category_fields)
            st.session_state.extraction_fields = sorted(
                default_fields, key=lambda f: f.display_order
            )
            st.success(f"Loaded {len(st.session_state.extraction_fields)} default fields")
            st.rerun()


def render_field_editor():
    """Render field editing interface."""
    if not st.session_state.get("extraction_fields"):
        return

    fields = st.session_state.extraction_fields

    st.header("Configure Extraction Fields")

    # Group by category
    categories = {}
    for field in fields:
        if field.category not in categories:
            categories[field.category] = []
        categories[field.category].append(field)

    # Display and edit each category
    updated_fields = []

    for category, cat_fields in categories.items():
        st.subheader(category.replace("_", " ").title())

        for i, field in enumerate(cat_fields):
            with st.expander(f"{'✅' if field.required else '⬜'} {field.field_name}", expanded=False):
                col1, col2 = st.columns(2)

                with col1:
                    new_name = st.text_input(
                        "Field Name",
                        value=field.field_name,
                        key=f"name_{field.id}"
                    )

                    new_desc = st.text_area(
                        "Description",
                        value=field.description,
                        key=f"desc_{field.id}",
                        height=80
                    )

                with col2:
                    new_type = st.selectbox(
                        "Field Type",
                        options=["text", "numeric", "categorical", "date", "boolean"],
                        index=["text", "numeric", "categorical", "date", "boolean"].index(field.field_type.value),
                        key=f"type_{field.id}"
                    )

                    new_required = st.checkbox(
                        "Required",
                        value=field.required,
                        key=f"req_{field.id}"
                    )

                # Options for categorical fields
                new_options = None
                if new_type == "categorical":
                    options_str = st.text_input(
                        "Options (comma-separated)",
                        value=", ".join(field.options) if field.options else "",
                        key=f"opts_{field.id}"
                    )
                    if options_str:
                        new_options = [o.strip() for o in options_str.split(",")]

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🗑️ Remove", key=f"remove_{field.id}"):
                        continue  # Skip adding this field

                # Create updated field
                updated_field = ExtractionField(
                    id=field.id,
                    field_name=new_name,
                    description=new_desc,
                    field_type=FieldType(new_type),
                    category=field.category,
                    required=new_required,
                    display_order=field.display_order,
                    options=new_options
                )
                updated_fields.append(updated_field)

    st.session_state.extraction_fields = updated_fields

    # Add new field
    st.divider()
    render_add_field()


def render_add_field():
    """Render interface for adding new fields."""
    st.subheader("Add New Field")

    with st.form("add_field_form"):
        col1, col2 = st.columns(2)

        with col1:
            new_name = st.text_input("Field Name", placeholder="e.g., sample_size")
            new_desc = st.text_area("Description", placeholder="e.g., Total number of participants")

        with col2:
            new_category = st.selectbox(
                "Category",
                options=["study_characteristics", "population", "intervention", "outcomes", "results", "quality"]
            )
            new_type = st.selectbox(
                "Field Type",
                options=["text", "numeric", "categorical", "date", "boolean"]
            )
            new_required = st.checkbox("Required")

        new_options = None
        if new_type == "categorical":
            options_str = st.text_input("Options (comma-separated)")
            if options_str:
                new_options = [o.strip() for o in options_str.split(",")]

        submitted = st.form_submit_button("➕ Add Field")

        if submitted and new_name and new_desc:
            new_field = ExtractionField(
                field_name=new_name,
                description=new_desc,
                field_type=FieldType(new_type),
                category=new_category,
                required=new_required,
                display_order=len(st.session_state.extraction_fields) * 10,
                options=new_options
            )
            st.session_state.extraction_fields.append(new_field)
            st.success(f"Added field: {new_name}")
            st.rerun()


def render_field_summary():
    """Render summary of configured fields."""
    if not st.session_state.get("extraction_fields"):
        return

    fields = st.session_state.extraction_fields

    st.header("Field Summary")

    # Summary table
    rows = []
    for field in fields:
        rows.append({
            "Field": field.field_name,
            "Type": field.field_type.value,
            "Category": field.category,
            "Required": "✅" if field.required else "",
            "Description": field.description[:50] + "..." if len(field.description) > 50 else field.description
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # Stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Fields", len(fields))

    with col2:
        required = sum(1 for f in fields if f.required)
        st.metric("Required Fields", required)

    with col3:
        categories = len(set(f.category for f in fields))
        st.metric("Categories", categories)


def save_fields():
    """Save configured fields to project."""
    if not st.session_state.get("extraction_fields"):
        st.error("No fields configured")
        return

    project = st.session_state.current_project
    project.extraction_fields = st.session_state.extraction_fields

    if st.session_state.get("session_manager"):
        st.session_state.session_manager.save_project(project)

    st.session_state.fields_configured = True
    st.success("Fields saved!")


def main():
    """Main function for Extraction Setup page."""
    st.set_page_config(
        page_title="Extraction Setup - Systematic Review App",
        page_icon="🔧",
        layout="wide"
    )

    init_session_state()
    render_sidebar()

    st.title("🔧 Extraction Setup")

    # Check prerequisites
    if not st.session_state.get("current_project"):
        st.warning("⚠️ Please set up a project first.")
        return

    # Load existing fields if available
    project = st.session_state.current_project
    if project.extraction_fields and not st.session_state.extraction_fields:
        st.session_state.extraction_fields = project.extraction_fields

    # Field recommendation
    render_field_recommendation()

    # Field editor
    if st.session_state.get("extraction_fields"):
        st.divider()
        render_field_editor()

        st.divider()
        render_field_summary()

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            if st.button("💾 Save Configuration", type="primary", use_container_width=True):
                save_fields()

        with col2:
            if st.button("🔄 Reset to Default", use_container_width=True):
                st.session_state.extraction_fields = None
                st.rerun()

        if st.session_state.fields_configured:
            st.success("""
            ✅ **Configuration Complete!**

            Proceed to **Data Extraction** to extract data from included studies.
            """)


if __name__ == "__main__":
    main()

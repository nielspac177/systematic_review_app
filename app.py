"""
Systematic Review Application

A Streamlit-based application for conducting systematic reviews using
LLM-powered screening and data extraction.

Run with: streamlit run app.py
"""

import streamlit as st
from pathlib import Path

# Configure page
st.set_page_config(
    page_title="Systematic Review App",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': """
        # Systematic Review App (ReviewPyPer)

        An LLM-powered tool for conducting systematic reviews.

        ## Features
        - LLM-assisted criteria generation
        - Title/Abstract screening
        - Full-text screening
        - Feedback loop for low-confidence decisions
        - Data extraction
        - Risk of Bias assessment (RoB 2, ROBINS-I, NOS, QUADAS-2, JBI)
        - PRISMA 2020 flow diagram
        - Cost tracking and budget limits
        - Audit trail logging

        Supports OpenAI (GPT-5, GPT-4) and Anthropic (Claude) models.

        ## Credits

        **Application Developer**
        Niels Pacheco-Barrios

        **Based on ReviewPyPer**
        Original software by Calvin Howard
        """
    }
)


def main():
    """Main application entry point."""
    st.title("📚 Systematic Review Application")

    st.markdown("""
    Welcome to the Systematic Review Application! This tool helps you conduct
    systematic reviews using LLM-powered screening and data extraction.

    ## Getting Started

    Use the sidebar to navigate through the review process:

    1. **📋 Setup Review** - Create a project, configure LLM, generate criteria
    2. **🔍 Search Strategy Wizard** - Build and translate search strategies
    3. **📑 Title/Abstract Screening** - Screen studies by title and abstract
    4. **📄 Full-text Screening** - Screen full-text PDFs
    5. **🔄 Feedback Review** - Re-review low-confidence exclusions
    6. **🔧 Extraction Setup** - Configure data extraction fields
    7. **📊 Data Extraction** - Extract data from included studies
    8. **⚖️ RoB Setup** - Configure Risk of Bias assessment tools
    9. **📋 Risk of Bias** - Assess risk of bias with AI assistance

    ---
    """)

    # Quick status overview
    render_status_overview()

    # Instructions
    with st.expander("📖 How to Use This App", expanded=True):
        st.markdown("""
        ### Step 1: Setup Your Review

        1. Go to **Setup Review** in the sidebar
        2. Create a new project with your research question
        3. Enter your API key (OpenAI or Anthropic)
        4. Set an optional budget limit
        5. Generate inclusion/exclusion criteria using AI

        ### Step 2: Screen Titles and Abstracts

        1. Go to **Title/Abstract Screening**
        2. Upload a CSV file with your search results
        3. Map the columns (Title, Abstract, PMID, etc.)
        4. Review the cost estimate
        5. Run the screening

        ### Step 3: Screen Full-Texts (Optional)

        1. Go to **Full-text Screening**
        2. Upload PDFs for included studies
        3. Extract text from PDFs
        4. Run full-text screening

        ### Step 4: Review Low-Confidence Decisions

        1. Go to **Feedback Review**
        2. Review studies flagged for re-review
        3. Accept or override AI recommendations

        ### Step 5: Extract Data

        1. Go to **Extraction Setup** to configure fields
        2. Go to **Data Extraction** to extract data
        3. Review and edit extracted values
        4. Export to CSV or Excel

        ### Tips

        - 💰 Set a budget limit to prevent unexpected costs
        - 📊 Check the PRISMA diagram to track progress
        - 📝 Export the audit trail for transparency
        - 🔄 Use the feedback loop to catch missed studies
        """)

    # Feature highlights
    st.markdown("---")
    st.header("Features")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### 🤖 LLM-Powered
        - OpenAI (GPT-5, GPT-4)
        - Anthropic (Claude 3.5, Claude 3)
        - JSON mode for reliable parsing
        """)

    with col2:
        st.markdown("""
        ### 📊 PRISMA 2020
        - Full flow diagram
        - Automatic count updates
        - Exclusion reason tracking
        """)

    with col3:
        st.markdown("""
        ### 💰 Cost Management
        - Upfront cost estimates
        - Budget limits
        - Cost tracking per operation
        """)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### 📝 Audit Trail
        - Log every LLM call
        - Record prompts and responses
        - Export for transparency
        """)

    with col2:
        st.markdown("""
        ### 🔄 Feedback Loop
        - Flag low-confidence decisions
        - AI re-review with inclusive mindset
        - User override capability
        """)

    with col3:
        st.markdown("""
        ### 📁 Project Management
        - Named projects
        - Save and load progress
        - User-specified storage
        """)

    # Additional features row
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### ⚖️ Risk of Bias
        - RoB 2, ROBINS-I, NOS, QUADAS-2, JBI
        - AI-assisted assessment
        - Traffic light visualizations
        """)

    with col2:
        st.markdown("""
        ### 🔍 Search Strategy
        - PICO-based strategy building
        - Multi-database translation
        - Deduplication tools
        """)

    with col3:
        st.markdown("""
        ### 📤 Export Options
        - CSV, Excel, DOCX exports
        - RevMan XML for RoB
        - Audit trail documentation
        """)

    # Credits section
    st.markdown("---")
    st.markdown("""
    ### Credits

    **Developed by Niels Pacheco-Barrios**

    Based on **ReviewPyPer** by Calvin Howard

    This application combines LLM-powered automation with rigorous systematic review
    methodology to help researchers conduct high-quality evidence syntheses.
    """)


def render_status_overview():
    """Render quick status overview."""
    st.header("Current Status")

    if st.session_state.get("current_project"):
        project = st.session_state.current_project

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Project", project.name)

        with col2:
            criteria_status = "✅ Set" if project.criteria else "⏳ Pending"
            st.metric("Criteria", criteria_status)

        with col3:
            llm_status = "✅ Connected" if st.session_state.get("llm_client") else "⏳ Pending"
            st.metric("LLM", llm_status)

        with col4:
            if st.session_state.get("cost_tracker"):
                st.metric("Cost", f"${st.session_state.cost_tracker.total_cost:.4f}")
            else:
                st.metric("Cost", "$0.00")

        # PRISMA summary
        if project.prisma_counts:
            st.markdown("### PRISMA Summary")
            counts = project.prisma_counts

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Identified", counts.records_identified_databases)

            with col2:
                st.metric("Screened", counts.records_screened)

            with col3:
                st.metric("Assessed", counts.reports_assessed)

            with col4:
                st.metric("Included", counts.studies_included)

    else:
        st.info("""
        👋 **No project loaded**

        Go to **Setup Review** in the sidebar to create or load a project.
        """)


def render_sidebar():
    """Render sidebar with navigation."""
    with st.sidebar:
        st.markdown("## Navigation")
        st.markdown("""
        - [Setup Review](./0_Setup_Review)
        - [Search Strategy](./1_Search_Strategy_Wizard)
        - [Title/Abstract Screening](./2_Title_Abstract_Screening)
        - [Full-text Screening](./3_Fulltext_Screening)
        - [Feedback Review](./4_Feedback_Review)
        - [Extraction Setup](./5_Extraction_Setup)
        - [Data Extraction](./6_Data_Extraction)
        - [RoB Setup](./7_RoB_Setup)
        - [Risk of Bias](./8_Risk_of_Bias)
        """)


if __name__ == "__main__":
    main()

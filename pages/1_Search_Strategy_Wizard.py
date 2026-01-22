"""Search Strategy Wizard - 7-step wizard for systematic review search strategies."""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import models directly to avoid circular import issues
from core.storage.models import (
    SearchStrategy, WizardState, ConceptBlock, PICOElement,
    ParsedReference, DeduplicationResult, Study
)
from core.search_strategy.pico_analyzer import PICOAnalyzer
from core.search_strategy.concept_builder import ConceptBuilder
from core.search_strategy.pubmed_generator import PubMedGenerator
from core.search_strategy.syntax_validator import SyntaxValidator
from core.search_strategy.db_translator import DatabaseTranslator
from core.file_parsers.ris_parser import RISParser
from core.file_parsers.nbib_parser import NBIBParser
from core.file_parsers.deduplicator import Deduplicator
from core.llm.cost_tracker import CostTracker, OperationType
from components.wizard_navigation import (
    render_wizard_progress, render_step_header,
    render_navigation_buttons, WizardNavigator
)
from components.concept_editor import render_concept_blocks_editor, render_pico_summary
from components.syntax_editor import (
    render_syntax_editor, render_strategy_display,
    render_validation_results, render_database_selector,
    render_strategy_comparison, render_undo_redo_controls
)
from components.dedup_review import (
    render_dedup_statistics, render_dedup_table,
    render_file_upload_section, render_export_options
)
from components.cost_display import render_cost_estimate, render_cost_tracker


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize session state variables."""
    if "wizard_state" not in st.session_state:
        st.session_state.wizard_state = WizardState()

    if "wizard_navigator" not in st.session_state:
        st.session_state.wizard_navigator = WizardNavigator()

    if "concept_builder" not in st.session_state:
        st.session_state.concept_builder = None

    if "pico_analysis" not in st.session_state:
        st.session_state.pico_analysis = None

    if "pubmed_strategy" not in st.session_state:
        st.session_state.pubmed_strategy = ""

    if "pubmed_history" not in st.session_state:
        st.session_state.pubmed_history = []

    if "pubmed_history_index" not in st.session_state:
        st.session_state.pubmed_history_index = -1

    if "translated_strategies" not in st.session_state:
        st.session_state.translated_strategies = {}

    if "dedup_result" not in st.session_state:
        st.session_state.dedup_result = None

    if "parsed_references" not in st.session_state:
        st.session_state.parsed_references = []


def get_wizard_state() -> WizardState:
    """Get current wizard state."""
    return st.session_state.wizard_state


def get_navigator() -> WizardNavigator:
    """Get wizard navigator."""
    return st.session_state.wizard_navigator


# =============================================================================
# STEP RENDERING FUNCTIONS
# =============================================================================

def render_step_1_research_question():
    """Step 1: Research Question Input."""
    render_step_header(
        1,
        description="Enter your research question or paste an existing PubMed search strategy."
    )

    state = get_wizard_state()
    nav = get_navigator()

    # Option tabs
    tab1, tab2 = st.tabs(["New Research Question", "Existing PubMed Strategy"])

    with tab1:
        research_question = st.text_area(
            "Research Question",
            value=state.research_question,
            height=150,
            placeholder="Example: What is the effectiveness of cognitive behavioral therapy compared to medication for treating depression in adults?",
            help="Enter your PICO-formatted research question",
        )

        if research_question != state.research_question:
            state.research_question = research_question

    with tab2:
        existing_strategy = st.text_area(
            "Paste Existing PubMed Strategy",
            value=state.existing_pubmed_strategy or "",
            height=300,
            placeholder="Paste your numbered PubMed search strategy here...",
            help="If you already have a PubMed strategy, paste it here to skip to database translation",
        )

        if existing_strategy:
            state.existing_pubmed_strategy = existing_strategy
            st.info("Having an existing strategy will allow you to skip to Step 5 (Database Translation).")

    # Navigation
    st.divider()

    col1, col2, col3 = st.columns([1, 1, 1])

    with col2:
        if state.existing_pubmed_strategy:
            if st.button("Skip to Translation →", use_container_width=True):
                st.session_state.pubmed_strategy = state.existing_pubmed_strategy
                nav.skip_to_step(5)
                st.rerun()

    with col3:
        next_enabled = bool(state.research_question or state.existing_pubmed_strategy)
        if st.button("Next →", use_container_width=True, disabled=not next_enabled, type="primary"):
            nav.next_step()
            st.rerun()


def render_step_2_pico_analysis():
    """Step 2: PICO Analysis."""
    render_step_header(
        2,
        description="AI analyzes your research question to identify PICO elements and search terms."
    )

    state = get_wizard_state()
    nav = get_navigator()

    if not state.research_question:
        st.warning("Please enter a research question in Step 1.")
        if st.button("← Back to Step 1"):
            nav.go_to_step(1)
            st.rerun()
        return

    st.markdown("**Research Question:**")
    st.info(state.research_question)

    # Check for LLM client
    if "llm_client" not in st.session_state or st.session_state.llm_client is None:
        st.error("Please configure an LLM provider in the Setup page first.")
        return

    # PICO Analysis section
    st.markdown("### PICO Analysis")

    if st.session_state.pico_analysis:
        st.success("PICO analysis complete! Review the elements below.")
        _display_pico_analysis(st.session_state.pico_analysis)

        if st.button("🔄 Re-analyze"):
            st.session_state.pico_analysis = None
            st.rerun()
    else:
        # Cost estimate
        if "cost_tracker" in st.session_state:
            estimate = st.session_state.cost_tracker.estimate_cost(
                st.session_state.llm_client,
                OperationType.PICO_ANALYSIS,
                n_items=1,
            )
            st.caption(f"Estimated cost: ${estimate.estimated_cost:.4f}")

        if st.button("🤖 Analyze Research Question", type="primary"):
            with st.spinner("Analyzing research question..."):
                try:
                    analyzer = PICOAnalyzer(
                        llm_client=st.session_state.llm_client,
                        cost_tracker=st.session_state.get("cost_tracker"),
                    )
                    analysis = analyzer.analyze(state.research_question)
                    st.session_state.pico_analysis = analysis

                    # Create concept blocks
                    concept_blocks = analyzer.create_concept_blocks(analysis)
                    st.session_state.concept_builder = ConceptBuilder(concept_blocks)

                    st.success("Analysis complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error during analysis: {str(e)}")

    # Navigation
    st.divider()
    action = render_navigation_buttons(
        current_step=2,
        completed_steps=nav.completed_steps,
        next_enabled=st.session_state.pico_analysis is not None,
    )

    if action == "back":
        nav.previous_step()
        st.rerun()
    elif action == "next":
        nav.next_step()
        st.rerun()


def _display_pico_analysis(analysis: dict):
    """Display PICO analysis results."""
    elements = ["population", "intervention", "comparison", "outcome"]

    cols = st.columns(2)
    for i, elem in enumerate(elements):
        if elem in analysis and analysis[elem]:
            with cols[i % 2]:
                data = analysis[elem]
                st.markdown(f"**{elem.upper()}**")
                st.markdown(f"*{data.get('label', '')}*")

                if data.get("primary_terms"):
                    st.markdown("Terms: " + ", ".join(data["primary_terms"][:5]))

                if data.get("mesh_terms"):
                    st.markdown("MeSH: " + ", ".join(data["mesh_terms"][:3]))

    if analysis.get("search_notes"):
        st.info(f"**Notes:** {analysis['search_notes']}")


def render_step_3_concept_blocks():
    """Step 3: Concept Block Editing."""
    render_step_header(
        3,
        description="Review and edit the search terms for each PICO element."
    )

    nav = get_navigator()

    if st.session_state.concept_builder is None:
        st.warning("Please complete PICO analysis first.")
        if st.button("← Back to Step 2"):
            nav.go_to_step(2)
            st.rerun()
        return

    # Summary
    st.markdown("### Concept Summary")
    render_pico_summary(st.session_state.concept_builder.concept_blocks)

    st.divider()

    # Concept block editor
    def on_block_update(block_id: str, updates: dict):
        builder = st.session_state.concept_builder
        builder.update_block(block_id, **updates)

    def on_block_delete(block_id: str):
        builder = st.session_state.concept_builder
        builder.remove_block(block_id)
        st.rerun()

    def on_block_add(block_data: dict):
        builder = st.session_state.concept_builder
        builder.create_new_block(**block_data)

    def on_suggest_terms(block_id: str):
        if "llm_client" in st.session_state:
            block = st.session_state.concept_builder.get_block(block_id)
            if block:
                analyzer = PICOAnalyzer(
                    llm_client=st.session_state.llm_client,
                    cost_tracker=st.session_state.get("cost_tracker"),
                )
                terms = block.pico_element.primary_terms + block.pico_element.synonyms
                suggestions = analyzer.suggest_additional_terms(
                    block.pico_element.label,
                    terms,
                )
                st.session_state[f"suggestions_{block_id}"] = suggestions

    render_concept_blocks_editor(
        blocks=st.session_state.concept_builder.concept_blocks,
        on_update=on_block_update,
        on_delete=on_block_delete,
        on_add=on_block_add,
        on_suggest=on_suggest_terms,
    )

    # Navigation
    st.divider()
    action = render_navigation_buttons(
        current_step=3,
        completed_steps=nav.completed_steps,
        next_enabled=len(st.session_state.concept_builder.concept_blocks) > 0,
    )

    if action == "back":
        nav.previous_step()
        st.rerun()
    elif action == "next":
        nav.next_step()
        st.rerun()


def render_step_4_pubmed_strategy():
    """Step 4: PubMed Strategy Generation."""
    render_step_header(
        4,
        description="Generate and refine your PubMed search strategy."
    )

    nav = get_navigator()

    if st.session_state.concept_builder is None or not st.session_state.concept_builder.concept_blocks:
        st.warning("Please add concept blocks first.")
        if st.button("← Back to Step 3"):
            nav.go_to_step(3)
            st.rerun()
        return

    # Check for LLM client
    if "llm_client" not in st.session_state or st.session_state.llm_client is None:
        st.error("Please configure an LLM provider in the Setup page first.")
        return

    # Generation section
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### PubMed Search Strategy")

    with col2:
        if st.button("🤖 Generate Strategy", type="primary"):
            with st.spinner("Generating PubMed strategy..."):
                try:
                    generator = PubMedGenerator(
                        llm_client=st.session_state.llm_client,
                        cost_tracker=st.session_state.get("cost_tracker"),
                    )
                    strategy = generator.generate(
                        st.session_state.concept_builder.concept_blocks
                    )
                    st.session_state.pubmed_strategy = strategy

                    # Add to history
                    st.session_state.pubmed_history.append(strategy)
                    st.session_state.pubmed_history_index = len(st.session_state.pubmed_history) - 1

                    st.success("Strategy generated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating strategy: {str(e)}")

    # Strategy editor
    if st.session_state.pubmed_strategy:
        # Undo/Redo controls
        if len(st.session_state.pubmed_history) > 1:
            render_undo_redo_controls(
                history=st.session_state.pubmed_history,
                current_index=st.session_state.pubmed_history_index,
                on_undo=lambda: _undo_strategy(),
                on_redo=lambda: _redo_strategy(),
            )

        # Editor
        new_strategy = render_syntax_editor(
            strategy=st.session_state.pubmed_strategy,
            database="PubMed",
            height=400,
            key="pubmed_editor",
        )

        if new_strategy != st.session_state.pubmed_strategy:
            st.session_state.pubmed_strategy = new_strategy
            # Add to history
            st.session_state.pubmed_history.append(new_strategy)
            st.session_state.pubmed_history_index = len(st.session_state.pubmed_history) - 1

        # Validation
        st.markdown("### Validation")

        if st.button("Validate Syntax"):
            validator = SyntaxValidator()
            result = validator.validate(st.session_state.pubmed_strategy, "PUBMED")
            render_validation_results(result)

    else:
        st.info("Click 'Generate Strategy' to create a PubMed search strategy from your concept blocks.")

    # Navigation
    st.divider()
    action = render_navigation_buttons(
        current_step=4,
        completed_steps=nav.completed_steps,
        next_enabled=bool(st.session_state.pubmed_strategy),
    )

    if action == "back":
        nav.previous_step()
        st.rerun()
    elif action == "next":
        nav.next_step()
        st.rerun()


def _undo_strategy():
    """Undo strategy change."""
    if st.session_state.pubmed_history_index > 0:
        st.session_state.pubmed_history_index -= 1
        st.session_state.pubmed_strategy = st.session_state.pubmed_history[
            st.session_state.pubmed_history_index
        ]
        st.rerun()


def _redo_strategy():
    """Redo strategy change."""
    if st.session_state.pubmed_history_index < len(st.session_state.pubmed_history) - 1:
        st.session_state.pubmed_history_index += 1
        st.session_state.pubmed_strategy = st.session_state.pubmed_history[
            st.session_state.pubmed_history_index
        ]
        st.rerun()


def render_step_5_db_translation():
    """Step 5: Database Translation."""
    render_step_header(
        5,
        description="Translate your PubMed strategy to other databases."
    )

    nav = get_navigator()
    state = get_wizard_state()

    # Get PubMed strategy
    pubmed_strategy = st.session_state.pubmed_strategy or state.existing_pubmed_strategy

    if not pubmed_strategy:
        st.warning("Please create a PubMed strategy first.")
        if st.button("← Back to Step 4"):
            nav.go_to_step(4)
            st.rerun()
        return

    # Check for LLM client
    if "llm_client" not in st.session_state or st.session_state.llm_client is None:
        st.error("Please configure an LLM provider in the Setup page first.")
        return

    # Show source strategy
    with st.expander("📋 Source PubMed Strategy", expanded=False):
        render_strategy_display(pubmed_strategy, "PubMed")

    # Database selection
    st.markdown("### Select Target Databases")

    selected_dbs = render_database_selector(
        selected=state.selected_databases,
        key="db_select_step5",
    )
    state.selected_databases = selected_dbs

    if not selected_dbs:
        st.info("Select at least one database to translate to.")

    # Translate button
    if selected_dbs:
        if st.button("🔄 Translate to Selected Databases", type="primary"):
            translator = DatabaseTranslator(
                llm_client=st.session_state.llm_client,
                cost_tracker=st.session_state.get("cost_tracker"),
            )

            progress = st.progress(0)
            status = st.empty()

            for i, db in enumerate(selected_dbs):
                status.text(f"Translating to {db}...")
                try:
                    translated = translator.translate(pubmed_strategy, db)
                    st.session_state.translated_strategies[db] = translated
                except Exception as e:
                    st.error(f"Error translating to {db}: {str(e)}")

                progress.progress((i + 1) / len(selected_dbs))

            status.text("Translation complete!")
            st.success(f"Translated to {len(selected_dbs)} databases!")

    # Show translations
    if st.session_state.translated_strategies:
        st.markdown("### Translated Strategies")
        render_strategy_comparison(st.session_state.translated_strategies)

    # Navigation
    st.divider()
    action = render_navigation_buttons(
        current_step=5,
        completed_steps=nav.completed_steps,
        next_enabled=bool(st.session_state.translated_strategies) or bool(pubmed_strategy),
    )

    if action == "back":
        nav.previous_step()
        st.rerun()
    elif action == "next":
        nav.next_step()
        st.rerun()


def render_step_6_deduplication():
    """Step 6: Reference Deduplication."""
    render_step_header(
        6,
        description="Upload reference files from database searches and remove duplicates."
    )

    nav = get_navigator()

    # File upload
    def on_files_uploaded(files):
        all_refs = []

        for uploaded_file in files:
            content = uploaded_file.read().decode("utf-8", errors="ignore")
            filename = uploaded_file.name

            # Detect format and parse
            if filename.endswith(".nbib") or NBIBParser.is_nbib_format(content):
                parser = NBIBParser(source_file=filename)
            else:
                # Assume RIS
                db_name = RISParser.detect_database_from_content(content)
                parser = RISParser(source_file=filename, default_database=db_name)

            refs = parser.parse(content)
            all_refs.extend(refs)

        st.session_state.parsed_references = all_refs
        st.success(f"Parsed {len(all_refs)} references from {len(files)} files")

        # Run deduplication
        deduplicator = Deduplicator()
        result = deduplicator.deduplicate(
            all_refs,
            project_id=st.session_state.get("current_project", {}).get("id", ""),
        )
        st.session_state.dedup_result = result

    render_file_upload_section(on_upload=on_files_uploaded)

    # Show results
    if st.session_state.dedup_result:
        st.divider()
        render_dedup_statistics(st.session_state.dedup_result)

        st.divider()
        st.markdown("### Reference List")

        show_dups = st.checkbox("Show only duplicates")
        render_dedup_table(st.session_state.dedup_result, show_duplicates_only=show_dups)

    # Navigation
    st.divider()
    action = render_navigation_buttons(
        current_step=6,
        completed_steps=nav.completed_steps,
        next_enabled=True,  # Can proceed without deduplication
        show_skip=True,
        skip_label="Skip Deduplication",
    )

    if action == "back":
        nav.previous_step()
        st.rerun()
    elif action == "next" or action == "skip":
        nav.next_step()
        st.rerun()


def render_step_7_review_export():
    """Step 7: Review and Export."""
    render_step_header(
        7,
        description="Review your search strategy and export for your systematic review."
    )

    nav = get_navigator()
    state = get_wizard_state()

    # Summary
    st.markdown("### Search Strategy Summary")

    # Research question
    if state.research_question:
        st.markdown("**Research Question:**")
        st.info(state.research_question)

    # Strategies
    st.markdown("### Database Strategies")

    pubmed_strategy = st.session_state.pubmed_strategy or state.existing_pubmed_strategy

    all_strategies = {"PubMed": pubmed_strategy} if pubmed_strategy else {}
    all_strategies.update(st.session_state.translated_strategies)

    if all_strategies:
        render_strategy_comparison(all_strategies)

    # Deduplication results
    if st.session_state.dedup_result:
        st.markdown("### Deduplication Results")
        result = st.session_state.dedup_result
        st.markdown(f"- **Total records:** {result.total_records}")
        st.markdown(f"- **Unique records:** {result.unique_records}")
        st.markdown(f"- **Duplicates removed:** {result.duplicate_count}")

    # Export options
    st.divider()
    st.markdown("### Export Options")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📄 Export DOCX Report", use_container_width=True):
            _export_docx_report()

    with col2:
        if st.session_state.dedup_result:
            if st.button("📊 Export References (CSV)", use_container_width=True):
                _export_references_csv()

    with col3:
        if st.session_state.dedup_result:
            if st.button("🔬 Send to Screening", use_container_width=True, type="primary"):
                _send_to_screening()

    # Navigation
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("← Back", use_container_width=True):
            nav.previous_step()
            st.rerun()

    with col2:
        if st.button("✅ Finish Wizard", use_container_width=True, type="primary"):
            st.success("Search strategy wizard complete!")
            st.balloons()


def _export_docx_report():
    """Export DOCX report."""
    try:
        from core.export.docx_generator import DOCXGenerator

        state = get_wizard_state()
        pubmed_strategy = st.session_state.pubmed_strategy or state.existing_pubmed_strategy

        all_strategies = {"PubMed": pubmed_strategy} if pubmed_strategy else {}
        all_strategies.update(st.session_state.translated_strategies)

        generator = DOCXGenerator()
        docx_bytes = generator.generate_search_report(
            research_question=state.research_question,
            strategies=all_strategies,
            dedup_result=st.session_state.dedup_result,
        )

        st.download_button(
            label="📥 Download DOCX Report",
            data=docx_bytes,
            file_name="search_strategy_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except ImportError:
        st.error("python-docx not installed. Install with: pip install python-docx")
    except Exception as e:
        st.error(f"Error generating report: {str(e)}")


def _export_references_csv():
    """Export references to CSV."""
    import csv
    import io

    if not st.session_state.dedup_result:
        return

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Title", "Authors", "Year", "Journal", "DOI", "PMID",
        "Source Database", "Source File", "Is Duplicate"
    ])

    # Data
    for ref in st.session_state.dedup_result.all_references:
        if not ref.is_duplicate:  # Only unique records
            writer.writerow([
                ref.title, ref.authors, ref.year, ref.journal,
                ref.doi, ref.pmid, ref.source_database, ref.source_file, ref.is_duplicate
            ])

    csv_data = output.getvalue()

    st.download_button(
        label="📥 Download CSV",
        data=csv_data,
        file_name="deduplicated_references.csv",
        mime="text/csv",
    )


def _send_to_screening():
    """Send deduplicated references to screening."""
    if not st.session_state.dedup_result:
        st.error("No references to send.")
        return

    # Get unique references
    deduplicator = Deduplicator()
    unique_refs = deduplicator.get_unique_references(st.session_state.dedup_result)

    # Convert to Study objects for screening
    from core.storage.models import Study

    studies = []
    for ref in unique_refs:
        study = Study(
            pmid=ref.pmid,
            doi=ref.doi,
            title=ref.title,
            abstract=ref.abstract,
            authors=ref.authors,
            year=ref.year,
            journal=ref.journal,
            source_database=ref.source_database,
        )
        studies.append(study)

    st.session_state.studies_from_wizard = studies
    st.success(f"✅ {len(studies)} unique references ready for screening!")
    st.info("Go to Title/Abstract Screening to continue with these references.")


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar():
    """Render sidebar content."""
    with st.sidebar:
        st.markdown("## Search Strategy Wizard")

        nav = get_navigator()

        # Progress
        st.markdown("### Progress")
        progress = nav.get_progress_percentage()
        st.progress(progress / 100)
        st.caption(f"{progress:.0f}% complete")

        st.divider()

        # Cost tracking
        if "cost_tracker" in st.session_state and st.session_state.cost_tracker:
            st.markdown("### Cost Summary")
            tracker = st.session_state.cost_tracker
            st.metric("Total Spent", f"${tracker.total_cost:.4f}")

            if tracker.budget_limit:
                st.metric("Remaining", f"${tracker.remaining_budget:.2f}")

        st.divider()

        # Quick navigation
        st.markdown("### Quick Navigation")
        for i in range(1, 8):
            step_name = [
                "Research Question",
                "PICO Analysis",
                "Concept Blocks",
                "PubMed Strategy",
                "DB Translation",
                "Deduplication",
                "Review & Export",
            ][i - 1]

            is_current = nav.current_step == i
            is_completed = i in nav.completed_steps

            if is_completed:
                icon = "✅"
            elif is_current:
                icon = "▶️"
            else:
                icon = "○"

            if nav.is_step_accessible(i) and not is_current:
                if st.button(f"{icon} {step_name}", key=f"nav_{i}", use_container_width=True):
                    nav.go_to_step(i)
                    st.rerun()
            else:
                style = "font-weight: bold;" if is_current else "color: gray;"
                st.markdown(f"<div style='{style}'>{icon} {step_name}</div>", unsafe_allow_html=True)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main function for Search Strategy Wizard page."""
    st.set_page_config(
        page_title="Search Strategy Wizard",
        page_icon="🔍",
        layout="wide",
    )

    init_session_state()

    # Title
    st.title("🔍 Search Strategy Wizard")

    # Sidebar
    render_sidebar()

    # Progress indicator
    nav = get_navigator()
    render_wizard_progress(
        current_step=nav.current_step,
        completed_steps=nav.completed_steps,
    )

    st.divider()

    # Render current step
    step_renderers = {
        1: render_step_1_research_question,
        2: render_step_2_pico_analysis,
        3: render_step_3_concept_blocks,
        4: render_step_4_pubmed_strategy,
        5: render_step_5_db_translation,
        6: render_step_6_deduplication,
        7: render_step_7_review_export,
    }

    renderer = step_renderers.get(nav.current_step)
    if renderer:
        renderer()


if __name__ == "__main__":
    main()

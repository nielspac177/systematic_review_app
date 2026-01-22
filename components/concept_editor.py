"""Editable PICO concept blocks component."""

import streamlit as st
from typing import Optional, Callable

from core.storage.models import ConceptBlock, PICOElement


def render_concept_block(
    block: ConceptBlock,
    on_update: Optional[Callable[[str, dict], None]] = None,
    on_delete: Optional[Callable[[str], None]] = None,
    on_suggest: Optional[Callable[[str], None]] = None,
    editable: bool = True,
    show_delete: bool = True,
    expanded: bool = True,
) -> None:
    """
    Render a single concept block with editing capabilities.

    Args:
        block: ConceptBlock to render
        on_update: Callback(block_id, updates) when block is updated
        on_delete: Callback(block_id) when block is deleted
        on_suggest: Callback(block_id) to get AI suggestions
        editable: Whether block is editable
        show_delete: Whether to show delete button
        expanded: Whether expander is expanded by default
    """
    element = block.pico_element
    element_colors = {
        "population": "blue",
        "intervention": "green",
        "comparison": "orange",
        "outcome": "red",
        "other": "gray",
    }
    color = element_colors.get(element.element_type, "gray")

    with st.expander(
        f"**{block.name}** ({element.element_type.upper()})",
        expanded=expanded,
    ):
        # Header with element info
        st.markdown(f"*{element.label}*")

        if editable:
            # Primary terms
            st.markdown("**Primary Terms**")
            new_primary = st.text_area(
                "One term per line",
                value="\n".join(element.primary_terms),
                height=100,
                key=f"primary_{block.id}",
                label_visibility="collapsed",
            )

            # Synonyms
            st.markdown("**Synonyms**")
            new_synonyms = st.text_area(
                "One synonym per line",
                value="\n".join(element.synonyms),
                height=100,
                key=f"synonyms_{block.id}",
                label_visibility="collapsed",
            )

            # MeSH terms
            st.markdown("**MeSH Terms**")
            new_mesh = st.text_area(
                "One MeSH term per line",
                value="\n".join(element.mesh_terms),
                height=75,
                key=f"mesh_{block.id}",
                label_visibility="collapsed",
            )

            # Notes
            st.markdown("**Notes**")
            new_notes = st.text_input(
                "Notes",
                value=element.notes,
                key=f"notes_{block.id}",
                label_visibility="collapsed",
            )

            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 1])

            with col1:
                if st.button("💾 Save", key=f"save_{block.id}"):
                    updates = {
                        "primary_terms": [t.strip() for t in new_primary.split("\n") if t.strip()],
                        "synonyms": [t.strip() for t in new_synonyms.split("\n") if t.strip()],
                        "mesh_terms": [t.strip() for t in new_mesh.split("\n") if t.strip()],
                        "notes": new_notes,
                    }
                    if on_update:
                        on_update(block.id, updates)
                    st.success("Saved!")

            with col2:
                if on_suggest:
                    if st.button("🤖 Suggest Terms", key=f"suggest_{block.id}"):
                        on_suggest(block.id)

            with col3:
                if show_delete and on_delete:
                    if st.button("🗑️ Delete", key=f"delete_{block.id}"):
                        on_delete(block.id)

        else:
            # Read-only display
            if element.primary_terms:
                st.markdown("**Primary Terms:** " + ", ".join(element.primary_terms))
            if element.synonyms:
                st.markdown("**Synonyms:** " + ", ".join(element.synonyms))
            if element.mesh_terms:
                st.markdown("**MeSH Terms:** " + ", ".join(element.mesh_terms))
            if element.notes:
                st.markdown(f"**Notes:** {element.notes}")


def render_concept_blocks_editor(
    blocks: list[ConceptBlock],
    on_update: Optional[Callable[[str, dict], None]] = None,
    on_delete: Optional[Callable[[str], None]] = None,
    on_add: Optional[Callable[[dict], None]] = None,
    on_suggest: Optional[Callable[[str], None]] = None,
    on_reorder: Optional[Callable[[list[str]], None]] = None,
    show_add_button: bool = True,
    show_reorder: bool = False,
) -> None:
    """
    Render a list of concept blocks with editing capabilities.

    Args:
        blocks: List of ConceptBlocks to render
        on_update: Callback when a block is updated
        on_delete: Callback when a block is deleted
        on_add: Callback when a new block is added
        on_suggest: Callback to get AI suggestions
        on_reorder: Callback when blocks are reordered
        show_add_button: Whether to show add new block button
        show_reorder: Whether to show reorder controls
    """
    if not blocks:
        st.info("No concept blocks defined. Add some to build your search strategy.")
    else:
        for i, block in enumerate(blocks):
            render_concept_block(
                block,
                on_update=on_update,
                on_delete=on_delete,
                on_suggest=on_suggest,
                expanded=i == 0,  # First block expanded
            )

    # Add new block section
    if show_add_button:
        st.divider()
        st.markdown("### Add New Concept")

        with st.form("add_concept_form"):
            name = st.text_input("Concept Name")
            element_type = st.selectbox(
                "PICO Element Type",
                ["population", "intervention", "comparison", "outcome", "other"],
            )
            label = st.text_input("Label/Description")
            primary_terms = st.text_area("Primary Terms (one per line)")
            synonyms = st.text_area("Synonyms (one per line)")
            mesh_terms = st.text_area("MeSH Terms (one per line)")

            if st.form_submit_button("Add Concept"):
                if name:
                    new_block = {
                        "name": name,
                        "element_type": element_type,
                        "label": label or name,
                        "primary_terms": [t.strip() for t in primary_terms.split("\n") if t.strip()],
                        "synonyms": [t.strip() for t in synonyms.split("\n") if t.strip()],
                        "mesh_terms": [t.strip() for t in mesh_terms.split("\n") if t.strip()],
                    }
                    if on_add:
                        on_add(new_block)
                    st.success(f"Added concept: {name}")
                    st.rerun()
                else:
                    st.error("Please enter a concept name")


def render_term_chips(
    terms: list[str],
    label: str,
    color: str = "blue",
    on_remove: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Render terms as removable chips/tags.

    Args:
        terms: List of terms to display
        label: Label for the chip group
        color: Color theme
        on_remove: Callback when a term is removed
    """
    if not terms:
        return

    st.markdown(f"**{label}:**")

    # Create columns for chips
    cols = st.columns(min(len(terms), 4))

    for i, term in enumerate(terms):
        with cols[i % 4]:
            if on_remove:
                if st.button(f"❌ {term}", key=f"chip_{label}_{i}"):
                    on_remove(term)
            else:
                st.markdown(
                    f"<span style='background-color: #{color}22; "
                    f"padding: 2px 8px; border-radius: 4px; "
                    f"border: 1px solid #{color};'>{term}</span>",
                    unsafe_allow_html=True,
                )


def render_pico_summary(blocks: list[ConceptBlock]) -> None:
    """
    Render a summary of PICO elements.

    Args:
        blocks: List of concept blocks
    """
    pico_order = ["population", "intervention", "comparison", "outcome", "other"]
    sorted_blocks = sorted(
        blocks,
        key=lambda b: pico_order.index(b.pico_element.element_type)
        if b.pico_element.element_type in pico_order
        else 999,
    )

    for block in sorted_blocks:
        elem = block.pico_element
        all_terms = elem.primary_terms + elem.synonyms
        term_count = len(all_terms) + len(elem.mesh_terms)

        st.markdown(
            f"**{elem.element_type.upper()}:** {block.name} "
            f"({term_count} terms)"
        )


def render_suggestions_dialog(
    suggestions: dict,
    on_accept: Callable[[list[str], str], None],
    block_id: str,
) -> None:
    """
    Render AI suggestions in a dialog.

    Args:
        suggestions: Dictionary with suggested terms
        on_accept: Callback(terms, term_type) when suggestions accepted
        block_id: Block ID for the suggestions
    """
    st.markdown("### AI Suggestions")

    if suggestions.get("suggested_synonyms"):
        st.markdown("**Suggested Synonyms:**")
        selected_synonyms = st.multiselect(
            "Select synonyms to add",
            suggestions["suggested_synonyms"],
            key=f"sel_syn_{block_id}",
        )
        if st.button("Add Selected Synonyms", key=f"add_syn_{block_id}"):
            on_accept(selected_synonyms, "synonym")

    if suggestions.get("suggested_mesh_terms"):
        st.markdown("**Suggested MeSH Terms:**")
        selected_mesh = st.multiselect(
            "Select MeSH terms to add",
            suggestions["suggested_mesh_terms"],
            key=f"sel_mesh_{block_id}",
        )
        if st.button("Add Selected MeSH Terms", key=f"add_mesh_{block_id}"):
            on_accept(selected_mesh, "mesh")

    if suggestions.get("suggested_abbreviations"):
        st.markdown("**Suggested Abbreviations:**")
        for abbr in suggestions["suggested_abbreviations"]:
            st.markdown(f"- {abbr}")

    if suggestions.get("rationale"):
        st.info(suggestions["rationale"])

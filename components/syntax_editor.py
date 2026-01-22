"""Search syntax editor component with highlighting."""

import streamlit as st
from typing import Optional, Callable
import re


def render_syntax_editor(
    strategy: str,
    database: str = "PubMed",
    on_change: Optional[Callable[[str], None]] = None,
    height: int = 400,
    show_line_numbers: bool = True,
    editable: bool = True,
    key: str = "syntax_editor",
) -> str:
    """
    Render a syntax editor for search strategies.

    Args:
        strategy: Current search strategy text
        database: Target database for syntax highlighting
        on_change: Callback when content changes
        height: Editor height in pixels
        show_line_numbers: Whether to show line numbers
        editable: Whether editor is editable
        key: Streamlit widget key

    Returns:
        Current editor content
    """
    # Try to use streamlit-ace if available
    try:
        from streamlit_ace import st_ace

        # Custom mode for search syntax could be added here
        content = st_ace(
            value=strategy,
            language="text",
            theme="github",
            height=height,
            key=key,
            readonly=not editable,
            show_gutter=show_line_numbers,
            wrap=True,
            auto_update=True,
        )

        if on_change and content != strategy:
            on_change(content)

        return content

    except ImportError:
        # Fallback to standard text area
        st.warning("Install streamlit-ace for better syntax editing: `pip install streamlit-ace`")

        content = st.text_area(
            "Search Strategy",
            value=strategy,
            height=height,
            key=key,
            disabled=not editable,
        )

        if on_change and content != strategy:
            on_change(content)

        return content


def render_strategy_display(
    strategy: str,
    database: str = "PubMed",
    show_line_numbers: bool = True,
    highlight_errors: Optional[list[dict]] = None,
) -> None:
    """
    Render a read-only strategy display with syntax highlighting.

    Args:
        strategy: Search strategy to display
        database: Database for syntax context
        show_line_numbers: Whether to show line numbers
        highlight_errors: List of error dicts with 'line' and 'message' keys
    """
    lines = strategy.split("\n")
    error_lines = {e["line"] for e in (highlight_errors or [])}

    html_lines = []
    for i, line in enumerate(lines, 1):
        # Apply syntax highlighting
        highlighted = _highlight_line(line, database)

        # Add error highlighting if needed
        if i in error_lines:
            bg_color = "#ffe0e0"
            border = "border-left: 3px solid red;"
        else:
            bg_color = "transparent"
            border = ""

        if show_line_numbers:
            line_num = f"<span style='color: gray; margin-right: 10px;'>{i:2d}.</span>"
        else:
            line_num = ""

        html_lines.append(
            f"<div style='background-color: {bg_color}; {border} "
            f"padding: 2px 5px; font-family: monospace;'>"
            f"{line_num}{highlighted}</div>"
        )

    html = "<div style='border: 1px solid #ddd; border-radius: 5px; padding: 10px;'>"
    html += "".join(html_lines)
    html += "</div>"

    st.markdown(html, unsafe_allow_html=True)


def _highlight_line(line: str, database: str) -> str:
    """Apply syntax highlighting to a line."""
    # Boolean operators
    line = re.sub(
        r'\b(AND|OR|NOT)\b',
        r'<span style="color: blue; font-weight: bold;">\1</span>',
        line,
        flags=re.IGNORECASE,
    )

    # Line references
    line = re.sub(
        r'(#\d+)',
        r'<span style="color: purple;">\1</span>',
        line,
    )

    # Field tags (PubMed style)
    line = re.sub(
        r'(\[[^\]]+\])',
        r'<span style="color: green;">\1</span>',
        line,
    )

    # Quoted phrases
    line = re.sub(
        r'("[^"]+")',
        r'<span style="color: brown;">\1</span>',
        line,
    )

    # Truncation
    line = re.sub(
        r'(\w+\*)',
        r'<span style="color: orange;">\1</span>',
        line,
    )

    return line


def render_validation_results(
    validation_result,
    show_warnings: bool = True,
) -> None:
    """
    Render validation results.

    Args:
        validation_result: ValidationResult object
        show_warnings: Whether to show warnings
    """
    if validation_result.is_valid:
        st.success(f"✅ {validation_result.summary}")
    else:
        st.error(f"❌ {validation_result.summary}")

    # Show errors
    if validation_result.errors:
        st.markdown("### Errors")
        for error in validation_result.errors:
            with st.expander(
                f"Line {error.line}: {error.error_type}",
                expanded=True,
            ):
                st.error(error.message)
                if error.suggestion:
                    st.info(f"💡 Suggestion: {error.suggestion}")

    # Show warnings
    if show_warnings and validation_result.warnings:
        st.markdown("### Warnings")
        for warning in validation_result.warnings:
            with st.expander(f"Line {warning.line}: {warning.warning_type}"):
                st.warning(warning.message)


def render_undo_redo_controls(
    history: list[str],
    current_index: int,
    on_undo: Callable,
    on_redo: Callable,
) -> None:
    """
    Render undo/redo controls for strategy editing.

    Args:
        history: List of strategy versions
        current_index: Current position in history
        on_undo: Callback for undo
        on_redo: Callback for redo
    """
    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
        can_undo = current_index > 0
        if st.button("↩️ Undo", disabled=not can_undo):
            on_undo()

    with col2:
        can_redo = current_index < len(history) - 1
        if st.button("↪️ Redo", disabled=not can_redo):
            on_redo()

    with col3:
        st.caption(f"Version {current_index + 1} of {len(history)}")


def render_database_selector(
    selected: list[str],
    available: list[str] = None,
    on_change: Optional[Callable[[list[str]], None]] = None,
    key: str = "db_selector",
) -> list[str]:
    """
    Render database selection checkboxes.

    Args:
        selected: Currently selected databases
        available: Available databases
        on_change: Callback when selection changes
        key: Widget key prefix

    Returns:
        List of selected databases
    """
    if available is None:
        available = ["SCOPUS", "WOS", "COCHRANE", "EMBASE", "OVID"]

    st.markdown("**Select Target Databases:**")

    cols = st.columns(len(available))
    new_selected = []

    for col, db in zip(cols, available):
        with col:
            is_selected = st.checkbox(
                db,
                value=db in selected,
                key=f"{key}_{db}",
            )
            if is_selected:
                new_selected.append(db)

    if on_change and new_selected != selected:
        on_change(new_selected)

    return new_selected


def render_strategy_comparison(
    strategies: dict[str, str],
    highlight_differences: bool = True,
) -> None:
    """
    Render side-by-side comparison of strategies.

    Args:
        strategies: Dictionary mapping database name to strategy
        highlight_differences: Whether to highlight differences
    """
    if not strategies:
        st.info("No strategies to compare")
        return

    tabs = st.tabs(list(strategies.keys()))

    for tab, (db_name, strategy) in zip(tabs, strategies.items()):
        with tab:
            st.markdown(f"### {db_name}")
            render_strategy_display(strategy, database=db_name)

            # Copy button
            st.text_area(
                "Copy to clipboard",
                value=strategy,
                height=100,
                key=f"copy_{db_name}",
                help="Select all and copy",
            )

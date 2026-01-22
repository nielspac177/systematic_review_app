"""Wizard navigation component for multi-step workflows."""

import streamlit as st
from typing import Callable, Optional


WIZARD_STEPS = [
    {"number": 1, "name": "Research Question", "icon": "1️⃣"},
    {"number": 2, "name": "PICO Analysis", "icon": "2️⃣"},
    {"number": 3, "name": "Concept Blocks", "icon": "3️⃣"},
    {"number": 4, "name": "PubMed Strategy", "icon": "4️⃣"},
    {"number": 5, "name": "DB Translation", "icon": "5️⃣"},
    {"number": 6, "name": "Deduplication", "icon": "6️⃣"},
    {"number": 7, "name": "Review & Export", "icon": "7️⃣"},
]


def render_wizard_progress(
    current_step: int,
    completed_steps: list[int],
    show_labels: bool = True,
) -> None:
    """
    Render wizard progress indicator.

    Args:
        current_step: Current step number (1-7)
        completed_steps: List of completed step numbers
        show_labels: Whether to show step labels
    """
    # Calculate progress
    progress = (current_step - 1) / (len(WIZARD_STEPS) - 1) if len(WIZARD_STEPS) > 1 else 0

    # Progress bar
    st.progress(progress)

    # Step indicators
    cols = st.columns(len(WIZARD_STEPS))

    for i, (col, step) in enumerate(zip(cols, WIZARD_STEPS)):
        with col:
            step_num = step["number"]
            is_current = step_num == current_step
            is_completed = step_num in completed_steps
            is_accessible = step_num <= current_step or is_completed

            if is_completed:
                status = "✅"
                style = "color: green;"
            elif is_current:
                status = "🔵"
                style = "font-weight: bold;"
            else:
                status = "⚪"
                style = "color: gray;"

            if show_labels:
                st.markdown(
                    f"<div style='text-align: center; {style}'>"
                    f"{status}<br><small>{step['name']}</small></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='text-align: center; {style}'>{status}</div>",
                    unsafe_allow_html=True,
                )


def render_step_header(
    step_number: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """
    Render step header with title and description.

    Args:
        step_number: Current step number
        title: Optional custom title (defaults to step name)
        description: Optional description text
    """
    step = WIZARD_STEPS[step_number - 1]
    display_title = title or step["name"]

    st.markdown(f"### Step {step_number}: {display_title}")

    if description:
        st.markdown(f"*{description}*")

    st.divider()


def render_navigation_buttons(
    current_step: int,
    completed_steps: list[int],
    on_back: Optional[Callable] = None,
    on_next: Optional[Callable] = None,
    on_skip: Optional[Callable] = None,
    next_enabled: bool = True,
    back_enabled: bool = True,
    next_label: str = "Next",
    back_label: str = "Back",
    show_skip: bool = False,
    skip_label: str = "Skip",
) -> Optional[str]:
    """
    Render navigation buttons and return clicked action.

    Args:
        current_step: Current step number
        completed_steps: List of completed step numbers
        on_back: Callback for back button
        on_next: Callback for next button
        on_skip: Callback for skip button
        next_enabled: Whether next button is enabled
        back_enabled: Whether back button is enabled
        next_label: Label for next button
        back_label: Label for back button
        show_skip: Whether to show skip button
        skip_label: Label for skip button

    Returns:
        "back", "next", "skip", or None
    """
    # Determine button states
    is_first_step = current_step == 1
    is_last_step = current_step == len(WIZARD_STEPS)

    # Layout columns
    if show_skip:
        col1, col2, col3 = st.columns([1, 1, 1])
    else:
        col1, col2 = st.columns([1, 1])

    action = None

    with col1:
        if not is_first_step and back_enabled:
            if st.button(f"← {back_label}", use_container_width=True):
                action = "back"
                if on_back:
                    on_back()

    if show_skip:
        with col2:
            if st.button(skip_label, use_container_width=True):
                action = "skip"
                if on_skip:
                    on_skip()
        button_col = col3
    else:
        button_col = col2

    with button_col:
        if is_last_step:
            button_text = "Finish"
        else:
            button_text = f"{next_label} →"

        if st.button(
            button_text,
            use_container_width=True,
            disabled=not next_enabled,
            type="primary",
        ):
            action = "next"
            if on_next:
                on_next()

    return action


def render_step_sidebar(
    current_step: int,
    completed_steps: list[int],
    on_step_click: Optional[Callable[[int], None]] = None,
) -> Optional[int]:
    """
    Render step navigation in sidebar.

    Args:
        current_step: Current step number
        completed_steps: List of completed step numbers
        on_step_click: Callback when a step is clicked

    Returns:
        Step number if clicked, None otherwise
    """
    st.sidebar.markdown("### Wizard Progress")

    clicked_step = None

    for step in WIZARD_STEPS:
        step_num = step["number"]
        is_current = step_num == current_step
        is_completed = step_num in completed_steps
        is_accessible = step_num <= current_step or step_num - 1 in completed_steps

        if is_completed:
            icon = "✅"
        elif is_current:
            icon = "▶️"
        else:
            icon = "○"

        label = f"{icon} {step['name']}"

        if is_accessible and not is_current:
            if st.sidebar.button(
                label,
                key=f"sidebar_step_{step_num}",
                use_container_width=True,
            ):
                clicked_step = step_num
                if on_step_click:
                    on_step_click(step_num)
        else:
            style = "font-weight: bold;" if is_current else "color: gray;"
            st.sidebar.markdown(
                f"<div style='{style}'>{label}</div>",
                unsafe_allow_html=True,
            )

    return clicked_step


class WizardNavigator:
    """Helper class for managing wizard navigation state."""

    def __init__(
        self,
        session_key: str = "wizard_step",
        completed_key: str = "wizard_completed",
        total_steps: int = 7,
    ):
        """
        Initialize wizard navigator.

        Args:
            session_key: Session state key for current step
            completed_key: Session state key for completed steps
            total_steps: Total number of steps
        """
        self.session_key = session_key
        self.completed_key = completed_key
        self.total_steps = total_steps

        # Initialize session state
        if session_key not in st.session_state:
            st.session_state[session_key] = 1
        if completed_key not in st.session_state:
            st.session_state[completed_key] = []

    @property
    def current_step(self) -> int:
        """Get current step number."""
        return st.session_state[self.session_key]

    @current_step.setter
    def current_step(self, value: int) -> None:
        """Set current step number."""
        st.session_state[self.session_key] = max(1, min(value, self.total_steps))

    @property
    def completed_steps(self) -> list[int]:
        """Get list of completed step numbers."""
        return st.session_state[self.completed_key]

    def complete_step(self, step: Optional[int] = None) -> None:
        """Mark a step as completed."""
        step = step or self.current_step
        if step not in self.completed_steps:
            st.session_state[self.completed_key].append(step)

    def go_to_step(self, step: int) -> None:
        """Navigate to a specific step."""
        self.current_step = step

    def next_step(self) -> None:
        """Navigate to next step."""
        self.complete_step()
        if self.current_step < self.total_steps:
            self.current_step += 1

    def previous_step(self) -> None:
        """Navigate to previous step."""
        if self.current_step > 1:
            self.current_step -= 1

    def skip_to_step(self, step: int) -> None:
        """Skip to a specific step, marking intermediate steps as completed."""
        for s in range(self.current_step, step):
            self.complete_step(s)
        self.current_step = step

    def reset(self) -> None:
        """Reset wizard to initial state."""
        st.session_state[self.session_key] = 1
        st.session_state[self.completed_key] = []

    def is_step_accessible(self, step: int) -> bool:
        """Check if a step is accessible."""
        return step <= self.current_step or step - 1 in self.completed_steps

    def get_progress_percentage(self) -> float:
        """Get overall progress as percentage."""
        return len(self.completed_steps) / self.total_steps * 100

"""Real-time progress bar component for Streamlit."""

import streamlit as st
from typing import Optional, Callable
import time


class ProgressTracker:
    """Track and display progress for long-running operations."""

    def __init__(
        self,
        total: int,
        description: str = "Processing",
        show_percentage: bool = True,
        show_count: bool = True,
        show_eta: bool = True,
    ):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items to process
            description: Description of the operation
            show_percentage: Whether to show percentage
            show_count: Whether to show current/total count
            show_eta: Whether to show estimated time remaining
        """
        self.total = total
        self.description = description
        self.show_percentage = show_percentage
        self.show_count = show_count
        self.show_eta = show_eta

        self.current = 0
        self.start_time = None
        self.status_text = ""

        # Streamlit components
        self._progress_bar = None
        self._status_placeholder = None
        self._metrics_placeholder = None

    def start(self) -> None:
        """Start the progress tracker and create UI elements."""
        self.start_time = time.time()
        self.current = 0

        # Create UI elements
        st.markdown(f"**{self.description}**")
        self._progress_bar = st.progress(0)
        self._status_placeholder = st.empty()
        self._metrics_placeholder = st.empty()

    def update(self, current: int, status: str = "") -> None:
        """
        Update progress.

        Args:
            current: Current item number (0-indexed)
            status: Status message to display
        """
        self.current = current + 1  # Convert to 1-indexed for display
        self.status_text = status

        if self._progress_bar is None:
            self.start()

        # Calculate progress
        progress = min(self.current / self.total, 1.0) if self.total > 0 else 0

        # Update progress bar
        self._progress_bar.progress(progress)

        # Update status text
        if self._status_placeholder and status:
            self._status_placeholder.markdown(f"*{status}*")

        # Update metrics
        if self._metrics_placeholder:
            metrics = self._build_metrics_text()
            self._metrics_placeholder.markdown(metrics)

    def _build_metrics_text(self) -> str:
        """Build metrics display text."""
        parts = []

        if self.show_count:
            parts.append(f"{self.current}/{self.total}")

        if self.show_percentage:
            pct = (self.current / self.total * 100) if self.total > 0 else 0
            parts.append(f"{pct:.1f}%")

        if self.show_eta and self.start_time and self.current > 0:
            elapsed = time.time() - self.start_time
            rate = self.current / elapsed
            remaining = (self.total - self.current) / rate if rate > 0 else 0
            if remaining < 60:
                parts.append(f"~{remaining:.0f}s remaining")
            else:
                parts.append(f"~{remaining/60:.1f}min remaining")

        return " | ".join(parts)

    def complete(self, message: str = "Complete!") -> None:
        """
        Mark progress as complete.

        Args:
            message: Completion message
        """
        if self._progress_bar:
            self._progress_bar.progress(1.0)

        if self._status_placeholder:
            self._status_placeholder.markdown(f"✅ **{message}**")

        if self._metrics_placeholder:
            elapsed = time.time() - self.start_time if self.start_time else 0
            self._metrics_placeholder.markdown(
                f"Processed {self.total} items in {elapsed:.1f}s"
            )

    def error(self, message: str) -> None:
        """
        Display an error.

        Args:
            message: Error message
        """
        if self._status_placeholder:
            self._status_placeholder.markdown(f"❌ **Error:** {message}")

    def get_callback(self) -> Callable[[int, int, str], None]:
        """
        Get a callback function for use with batch processing functions.

        Returns:
            Callback function(current, total, status)
        """
        def callback(current: int, total: int, status: str) -> None:
            if self._progress_bar is None:
                self.total = total
                self.start()
            self.update(current, status)

        return callback


def render_simple_progress(
    current: int,
    total: int,
    label: str = "Progress",
) -> None:
    """
    Render a simple progress indicator.

    Args:
        current: Current count
        total: Total count
        label: Label to display
    """
    progress = current / total if total > 0 else 0
    st.progress(progress)
    st.caption(f"{label}: {current}/{total} ({progress*100:.1f}%)")


def render_phase_progress(
    phases: list[dict],
    current_phase: int,
) -> None:
    """
    Render a multi-phase progress indicator.

    Args:
        phases: List of phase dicts with 'name' and 'status' keys
        current_phase: Index of current phase (0-indexed)
    """
    cols = st.columns(len(phases))

    for i, (col, phase) in enumerate(zip(cols, phases)):
        with col:
            if i < current_phase:
                # Completed
                st.markdown(f"✅ **{phase['name']}**")
            elif i == current_phase:
                # Current
                st.markdown(f"🔄 **{phase['name']}**")
                if 'progress' in phase:
                    st.progress(phase['progress'])
            else:
                # Pending
                st.markdown(f"⏳ {phase['name']}")


class BatchProgressContext:
    """Context manager for batch processing with progress."""

    def __init__(
        self,
        total: int,
        description: str = "Processing",
    ):
        """
        Initialize batch progress context.

        Args:
            total: Total items to process
            description: Description of operation
        """
        self.tracker = ProgressTracker(total, description)

    def __enter__(self) -> ProgressTracker:
        """Enter context and start tracking."""
        self.tracker.start()
        return self.tracker

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and complete tracking."""
        if exc_type is None:
            self.tracker.complete()
        else:
            self.tracker.error(str(exc_val))

"""Cost display and budget management components for Streamlit."""

import streamlit as st
from typing import Optional

from core.llm.cost_tracker import CostTracker, CostEstimate, OperationType


def render_cost_estimate(
    estimate: CostEstimate,
    budget_limit: Optional[float] = None,
    show_details: bool = True,
) -> bool:
    """
    Render a cost estimate with optional confirmation.

    Args:
        estimate: CostEstimate object
        budget_limit: Optional budget limit
        show_details: Whether to show detailed breakdown

    Returns:
        True if user confirms, False otherwise
    """
    st.markdown("### Cost Estimate")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Estimated Cost",
            f"${estimate.estimated_cost:.4f}",
            help="Estimated cost based on average token usage"
        )

    with col2:
        st.metric(
            "Items to Process",
            f"{estimate.n_items:,}",
        )

    if show_details:
        with st.expander("Cost Details"):
            st.markdown(f"""
            - **Model:** {estimate.model}
            - **Avg Input Tokens:** {estimate.avg_input_tokens:,}
            - **Avg Output Tokens:** {estimate.avg_output_tokens:,}
            - **Total Input Tokens:** {estimate.avg_input_tokens * estimate.n_items:,}
            - **Total Output Tokens:** {estimate.avg_output_tokens * estimate.n_items:,}
            """)

    # Budget warning
    if budget_limit is not None:
        if estimate.estimated_cost > budget_limit:
            st.error(
                f"⚠️ Estimated cost (${estimate.estimated_cost:.4f}) exceeds "
                f"budget limit (${budget_limit:.2f})"
            )
            return False
        else:
            remaining = budget_limit - estimate.estimated_cost
            st.success(
                f"✅ Within budget. Remaining after operation: ${remaining:.4f}"
            )

    return True


def render_cost_tracker(
    tracker: CostTracker,
    show_breakdown: bool = True,
) -> None:
    """
    Render current cost tracking status.

    Args:
        tracker: CostTracker object
        show_breakdown: Whether to show breakdown by operation
    """
    st.markdown("### Cost Tracking")

    # Main metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Total Spent",
            f"${tracker.total_cost:.4f}",
        )

    with col2:
        if tracker.budget_limit:
            remaining = tracker.remaining_budget or 0
            st.metric(
                "Remaining Budget",
                f"${remaining:.4f}",
                delta=f"-${tracker.total_cost:.4f}" if tracker.total_cost > 0 else None,
                delta_color="inverse"
            )
        else:
            st.metric("Budget Limit", "Not set")

    with col3:
        st.metric(
            "API Calls",
            f"{len(tracker.entries):,}",
        )

    # Budget progress bar
    if tracker.budget_limit:
        progress = min(tracker.total_cost / tracker.budget_limit, 1.0)
        st.progress(progress)

        if progress >= 0.9:
            st.warning("⚠️ Approaching budget limit!")
        elif progress >= 1.0:
            st.error("❌ Budget limit exceeded!")

    # Breakdown by operation
    if show_breakdown:
        summary = tracker.get_summary()
        by_op = summary.get("by_operation", {})

        if by_op:
            with st.expander("Cost Breakdown by Operation"):
                for op_name, op_data in by_op.items():
                    st.markdown(f"""
                    **{op_name.replace('_', ' ').title()}**
                    - Calls: {op_data['count']}
                    - Cost: ${op_data['total_cost']:.4f}
                    - Tokens: {op_data['total_input_tokens']:,} in / {op_data['total_output_tokens']:,} out
                    """)


def render_budget_input(
    current_limit: Optional[float] = None,
    key: str = "budget_limit",
) -> Optional[float]:
    """
    Render budget limit input.

    Args:
        current_limit: Current budget limit
        key: Streamlit widget key

    Returns:
        New budget limit or None
    """
    st.markdown("### Budget Settings")

    enable_budget = st.checkbox(
        "Enable budget limit",
        value=current_limit is not None,
        key=f"{key}_enable",
    )

    if enable_budget:
        limit = st.number_input(
            "Budget Limit (USD)",
            min_value=0.01,
            max_value=100.0,
            value=current_limit or 5.0,
            step=0.50,
            format="%.2f",
            key=key,
            help="Maximum amount to spend on LLM API calls"
        )

        # Show some reference costs
        with st.expander("Cost Reference"):
            st.markdown("""
            **Approximate costs per 1000 studies:**
            - Title/Abstract Screening (GPT-4o): ~$3.00
            - Title/Abstract Screening (Claude 3.5): ~$2.00
            - Full-text Screening: ~$20-40 (depends on PDF length)
            - Data Extraction: ~$15-30 per study
            """)

        return limit

    return None


def render_cost_confirmation(
    operation: str,
    estimated_cost: float,
    n_items: int,
    budget_limit: Optional[float] = None,
    current_spent: float = 0.0,
) -> bool:
    """
    Render cost confirmation dialog.

    Args:
        operation: Name of operation
        estimated_cost: Estimated cost
        n_items: Number of items
        budget_limit: Optional budget limit
        current_spent: Amount already spent

    Returns:
        True if user confirms
    """
    st.markdown(f"### Confirm {operation}")

    st.info(f"""
    **Operation:** {operation}
    **Items to process:** {n_items:,}
    **Estimated cost:** ${estimated_cost:.4f}
    """)

    if budget_limit:
        total_after = current_spent + estimated_cost
        st.markdown(f"""
        **Current spent:** ${current_spent:.4f}
        **After operation:** ${total_after:.4f}
        **Budget limit:** ${budget_limit:.2f}
        """)

        if total_after > budget_limit:
            st.error("⚠️ This operation would exceed your budget limit!")
            return False

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Proceed", type="primary", use_container_width=True):
            return True

    with col2:
        if st.button("❌ Cancel", use_container_width=True):
            st.warning("Operation cancelled")
            return False

    return False


def render_cost_summary_card(
    tracker: CostTracker,
    compact: bool = False,
) -> None:
    """
    Render a compact cost summary card for sidebar.

    Args:
        tracker: CostTracker object
        compact: Whether to use compact layout
    """
    if compact:
        st.markdown("**💰 Cost Summary**")
        st.markdown(f"Spent: **${tracker.total_cost:.4f}**")
        if tracker.budget_limit:
            remaining = tracker.remaining_budget or 0
            st.markdown(f"Remaining: **${remaining:.4f}**")
            progress = min(tracker.total_cost / tracker.budget_limit, 1.0)
            st.progress(progress)
    else:
        with st.container():
            st.markdown("### 💰 Cost Summary")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Spent", f"${tracker.total_cost:.4f}")
            with col2:
                if tracker.budget_limit:
                    st.metric("Remaining", f"${tracker.remaining_budget:.4f}")

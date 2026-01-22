"""UI components for systematic review application."""

from .prisma_diagram import (
    render_prisma_diagram,
    render_prisma_mini,
    update_prisma_counts,
)
from .progress_bar import (
    ProgressTracker,
    render_simple_progress,
    render_phase_progress,
    BatchProgressContext,
)
from .cost_display import (
    render_cost_estimate,
    render_cost_tracker,
    render_budget_input,
    render_cost_confirmation,
    render_cost_summary_card,
)
from .wizard_navigation import (
    render_wizard_progress,
    render_step_header,
    render_navigation_buttons,
    render_step_sidebar,
    WizardNavigator,
    WIZARD_STEPS,
)
from .concept_editor import (
    render_concept_block,
    render_concept_blocks_editor,
    render_term_chips,
    render_pico_summary,
    render_suggestions_dialog,
)
from .syntax_editor import (
    render_syntax_editor,
    render_strategy_display,
    render_validation_results,
    render_undo_redo_controls,
    render_database_selector,
    render_strategy_comparison,
)
from .dedup_review import (
    render_dedup_statistics,
    render_dedup_table,
    render_duplicate_review,
    render_file_upload_section,
    render_export_options,
)
from .traffic_light_plot import (
    render_traffic_light_plot,
    render_rob_table_simple,
    render_judgment_legend,
    render_distribution_chart,
    render_rob_summary_metrics,
)
from .rob_judgment_form import (
    render_signaling_question,
    render_domain_judgment_form,
    render_assessment_form,
)
from .rob_summary_table import (
    render_rob_summary_table,
    render_domain_summary,
    render_flagged_items,
    render_verification_progress,
    render_export_options as render_rob_export_options,
)
from .reference_import import (
    render_reference_import,
    convert_references_to_dataframe,
    detect_format,
    parse_uploaded_files,
)

__all__ = [
    # PRISMA
    "render_prisma_diagram",
    "render_prisma_mini",
    "update_prisma_counts",
    # Progress
    "ProgressTracker",
    "render_simple_progress",
    "render_phase_progress",
    "BatchProgressContext",
    # Cost
    "render_cost_estimate",
    "render_cost_tracker",
    "render_budget_input",
    "render_cost_confirmation",
    "render_cost_summary_card",
    # Wizard Navigation
    "render_wizard_progress",
    "render_step_header",
    "render_navigation_buttons",
    "render_step_sidebar",
    "WizardNavigator",
    "WIZARD_STEPS",
    # Concept Editor
    "render_concept_block",
    "render_concept_blocks_editor",
    "render_term_chips",
    "render_pico_summary",
    "render_suggestions_dialog",
    # Syntax Editor
    "render_syntax_editor",
    "render_strategy_display",
    "render_validation_results",
    "render_undo_redo_controls",
    "render_database_selector",
    "render_strategy_comparison",
    # Dedup Review
    "render_dedup_statistics",
    "render_dedup_table",
    "render_duplicate_review",
    "render_file_upload_section",
    "render_export_options",
    # Traffic Light Plot
    "render_traffic_light_plot",
    "render_rob_table_simple",
    "render_judgment_legend",
    "render_distribution_chart",
    "render_rob_summary_metrics",
    # RoB Judgment Form
    "render_signaling_question",
    "render_domain_judgment_form",
    "render_assessment_form",
    # RoB Summary Table
    "render_rob_summary_table",
    "render_domain_summary",
    "render_flagged_items",
    "render_verification_progress",
    "render_rob_export_options",
    # Reference Import
    "render_reference_import",
    "convert_references_to_dataframe",
    "detect_format",
    "parse_uploaded_files",
]

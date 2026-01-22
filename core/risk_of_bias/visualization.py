"""Visualization components for Risk of Bias assessments.

Provides traffic light plots and summary tables for RoB results.
"""

from typing import Optional
import pandas as pd

from ..storage.models import StudyRoBAssessment, JudgmentLevel, Study


# Color schemes for different judgment levels
JUDGMENT_COLORS = {
    JudgmentLevel.LOW: "#00B050",           # Green
    JudgmentLevel.SOME_CONCERNS: "#FFFF00", # Yellow
    JudgmentLevel.MODERATE: "#FFC000",      # Orange
    JudgmentLevel.SERIOUS: "#FF6600",       # Dark Orange
    JudgmentLevel.CRITICAL: "#C00000",      # Dark Red
    JudgmentLevel.HIGH: "#FF0000",          # Red
    JudgmentLevel.UNCLEAR: "#808080",       # Gray
    JudgmentLevel.NOT_APPLICABLE: "#FFFFFF", # White
    JudgmentLevel.NO_INFORMATION: "#D9D9D9", # Light Gray
}

# Symbols for accessibility
JUDGMENT_SYMBOLS = {
    JudgmentLevel.LOW: "+",
    JudgmentLevel.SOME_CONCERNS: "?",
    JudgmentLevel.MODERATE: "~",
    JudgmentLevel.SERIOUS: "-",
    JudgmentLevel.CRITICAL: "x",
    JudgmentLevel.HIGH: "-",
    JudgmentLevel.UNCLEAR: "?",
    JudgmentLevel.NOT_APPLICABLE: "NA",
    JudgmentLevel.NO_INFORMATION: "NI",
}

# Display names
JUDGMENT_LABELS = {
    JudgmentLevel.LOW: "Low Risk",
    JudgmentLevel.SOME_CONCERNS: "Some Concerns",
    JudgmentLevel.MODERATE: "Moderate",
    JudgmentLevel.SERIOUS: "Serious",
    JudgmentLevel.CRITICAL: "Critical",
    JudgmentLevel.HIGH: "High Risk",
    JudgmentLevel.UNCLEAR: "Unclear",
    JudgmentLevel.NOT_APPLICABLE: "N/A",
    JudgmentLevel.NO_INFORMATION: "No Info",
}


class TrafficLightPlot:
    """Generate traffic light plots for RoB visualization."""

    def __init__(
        self,
        assessments: list[StudyRoBAssessment],
        studies: Optional[list[Study]] = None,
    ):
        """
        Initialize traffic light plot.

        Args:
            assessments: List of RoB assessments
            studies: Optional list of studies for labels
        """
        self.assessments = assessments
        self.studies = studies
        self._study_map = {}
        if studies:
            self._study_map = {s.id: s for s in studies}

    def _get_study_label(self, study_id: str) -> str:
        """Get display label for a study."""
        if study_id in self._study_map:
            study = self._study_map[study_id]
            # Format as "Author (Year)" or just title if no author
            if study.authors and study.year:
                first_author = study.authors.split(",")[0].split(" ")[-1]
                return f"{first_author} ({study.year})"
            elif study.year:
                return f"{study.title[:30]} ({study.year})"
            else:
                return study.title[:40]
        return study_id[:20]

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert assessments to a DataFrame for plotting.

        Returns:
            DataFrame with studies as rows, domains as columns
        """
        if not self.assessments:
            return pd.DataFrame()

        # Get all unique domains (preserving order from first assessment)
        domains = []
        if self.assessments:
            domains = [dj.domain_name for dj in self.assessments[0].domain_judgments]

        rows = []
        for assessment in self.assessments:
            row = {
                "study_id": assessment.study_id,
                "study_label": self._get_study_label(assessment.study_id),
            }

            # Add domain judgments
            domain_map = {dj.domain_name: dj for dj in assessment.domain_judgments}
            for domain in domains:
                if domain in domain_map:
                    dj = domain_map[domain]
                    row[domain] = dj.judgment.value
                    row[f"{domain}_color"] = JUDGMENT_COLORS.get(dj.judgment, "#808080")
                    row[f"{domain}_symbol"] = JUDGMENT_SYMBOLS.get(dj.judgment, "?")
                else:
                    row[domain] = "unclear"
                    row[f"{domain}_color"] = "#808080"
                    row[f"{domain}_symbol"] = "?"

            # Add overall judgment
            row["Overall"] = assessment.overall_judgment.value
            row["Overall_color"] = JUDGMENT_COLORS.get(assessment.overall_judgment, "#808080")
            row["Overall_symbol"] = JUDGMENT_SYMBOLS.get(assessment.overall_judgment, "?")

            rows.append(row)

        return pd.DataFrame(rows)

    def create_plotly_figure(self, include_overall: bool = True):
        """
        Create a Plotly figure for the traffic light plot.

        Args:
            include_overall: Whether to include overall judgment column

        Returns:
            Plotly Figure object
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            raise ImportError("plotly is required for traffic light plots. Install with: pip install plotly")

        df = self.to_dataframe()
        if df.empty:
            return go.Figure()

        # Get domain columns (excluding metadata columns)
        metadata_cols = ['study_id', 'study_label']
        all_cols = [c for c in df.columns if not c.endswith('_color') and not c.endswith('_symbol') and c not in metadata_cols]

        if not include_overall:
            all_cols = [c for c in all_cols if c != 'Overall']

        # Create figure
        fig = go.Figure()

        # Add cells for each study and domain
        for i, row in df.iterrows():
            for j, domain in enumerate(all_cols):
                color = row.get(f"{domain}_color", "#808080")
                symbol = row.get(f"{domain}_symbol", "?")

                fig.add_trace(go.Scatter(
                    x=[j],
                    y=[i],
                    mode='markers+text',
                    marker=dict(
                        size=30,
                        color=color,
                        line=dict(color='black', width=1)
                    ),
                    text=symbol,
                    textposition='middle center',
                    textfont=dict(color='black', size=14, family='Arial Black'),
                    showlegend=False,
                    hovertext=f"{row['study_label']}<br>{domain}: {JUDGMENT_LABELS.get(JudgmentLevel(row[domain]), row[domain])}",
                    hoverinfo='text',
                ))

        # Update layout
        fig.update_layout(
            title="Risk of Bias Summary",
            xaxis=dict(
                tickmode='array',
                tickvals=list(range(len(all_cols))),
                ticktext=all_cols,
                tickangle=45,
                side='top',
            ),
            yaxis=dict(
                tickmode='array',
                tickvals=list(range(len(df))),
                ticktext=df['study_label'].tolist(),
                autorange='reversed',
            ),
            height=max(400, 50 * len(df) + 100),
            width=max(600, 80 * len(all_cols) + 200),
            margin=dict(l=200, r=50, t=150, b=50),
            plot_bgcolor='white',
        )

        return fig

    def create_matplotlib_figure(self, include_overall: bool = True):
        """
        Create a Matplotlib figure for the traffic light plot.

        Args:
            include_overall: Whether to include overall judgment column

        Returns:
            Matplotlib Figure object
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
        except ImportError:
            raise ImportError("matplotlib is required. Install with: pip install matplotlib")

        df = self.to_dataframe()
        if df.empty:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "No data", ha='center', va='center')
            return fig

        # Get domain columns
        metadata_cols = ['study_id', 'study_label']
        all_cols = [c for c in df.columns if not c.endswith('_color') and not c.endswith('_symbol') and c not in metadata_cols]

        if not include_overall:
            all_cols = [c for c in all_cols if c != 'Overall']

        n_rows = len(df)
        n_cols = len(all_cols)

        fig, ax = plt.subplots(figsize=(max(8, n_cols * 1.2), max(4, n_rows * 0.5)))

        for i, row in df.iterrows():
            for j, domain in enumerate(all_cols):
                color = row.get(f"{domain}_color", "#808080")
                symbol = row.get(f"{domain}_symbol", "?")

                circle = mpatches.Circle((j + 0.5, n_rows - i - 0.5), 0.35,
                                         facecolor=color, edgecolor='black', linewidth=1)
                ax.add_patch(circle)
                ax.text(j + 0.5, n_rows - i - 0.5, symbol,
                       ha='center', va='center', fontsize=10, fontweight='bold')

        # Set up axes
        ax.set_xlim(0, n_cols)
        ax.set_ylim(0, n_rows)
        ax.set_xticks([i + 0.5 for i in range(n_cols)])
        ax.set_xticklabels(all_cols, rotation=45, ha='right')
        ax.set_yticks([n_rows - i - 0.5 for i in range(n_rows)])
        ax.set_yticklabels(df['study_label'].tolist())
        ax.set_aspect('equal')
        ax.set_title('Risk of Bias Summary')

        plt.tight_layout()
        return fig


def create_summary_table(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
) -> pd.DataFrame:
    """
    Create a summary table of RoB assessments.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies for labels

    Returns:
        DataFrame with summary information
    """
    study_map = {}
    if studies:
        study_map = {s.id: s for s in studies}

    rows = []
    for assessment in assessments:
        study = study_map.get(assessment.study_id)

        row = {
            "Study ID": assessment.study_id,
            "Study": study.title[:50] if study else assessment.study_id[:20],
            "Authors": study.authors.split(",")[0] if study and study.authors else "Unknown",
            "Year": study.year if study else None,
            "Tool": assessment.tool_type.value,
            "Overall Judgment": JUDGMENT_LABELS.get(assessment.overall_judgment, assessment.overall_judgment.value),
            "Status": assessment.assessment_status,
        }

        # Add domain summaries
        for dj in assessment.domain_judgments:
            row[dj.domain_name] = JUDGMENT_LABELS.get(dj.judgment, dj.judgment.value)

        # Add flags
        flagged = sum(1 for dj in assessment.domain_judgments if dj.is_flagged_uncertain)
        verified = sum(1 for dj in assessment.domain_judgments if dj.is_human_verified)
        total = len(assessment.domain_judgments)

        row["Flagged"] = flagged
        row["Verified"] = f"{verified}/{total}"

        rows.append(row)

    return pd.DataFrame(rows)


def get_judgment_distribution(assessments: list[StudyRoBAssessment]) -> dict:
    """
    Get distribution of overall judgments.

    Args:
        assessments: List of assessments

    Returns:
        Dict with judgment level counts
    """
    distribution = {}
    for assessment in assessments:
        label = JUDGMENT_LABELS.get(assessment.overall_judgment, assessment.overall_judgment.value)
        distribution[label] = distribution.get(label, 0) + 1
    return distribution


def get_domain_distribution(assessments: list[StudyRoBAssessment]) -> dict:
    """
    Get distribution of judgments by domain.

    Args:
        assessments: List of assessments

    Returns:
        Dict with domain -> judgment -> count
    """
    distribution = {}
    for assessment in assessments:
        for dj in assessment.domain_judgments:
            if dj.domain_name not in distribution:
                distribution[dj.domain_name] = {}
            label = JUDGMENT_LABELS.get(dj.judgment, dj.judgment.value)
            distribution[dj.domain_name][label] = distribution[dj.domain_name].get(label, 0) + 1
    return distribution


def create_distribution_chart(assessments: list[StudyRoBAssessment], chart_type: str = "bar"):
    """
    Create a distribution chart for overall judgments.

    Args:
        assessments: List of assessments
        chart_type: "bar" or "pie"

    Returns:
        Plotly Figure
    """
    try:
        import plotly.express as px
        import plotly.graph_objects as go
    except ImportError:
        raise ImportError("plotly is required. Install with: pip install plotly")

    distribution = get_judgment_distribution(assessments)

    # Define order and colors
    order = ["Low Risk", "Some Concerns", "Moderate", "Serious", "Critical", "High Risk", "Unclear"]
    colors = {
        "Low Risk": "#00B050",
        "Some Concerns": "#FFFF00",
        "Moderate": "#FFC000",
        "Serious": "#FF6600",
        "Critical": "#C00000",
        "High Risk": "#FF0000",
        "Unclear": "#808080",
    }

    # Filter to only present categories
    categories = [c for c in order if c in distribution]
    values = [distribution.get(c, 0) for c in categories]
    category_colors = [colors.get(c, "#808080") for c in categories]

    if chart_type == "pie":
        fig = go.Figure(data=[go.Pie(
            labels=categories,
            values=values,
            marker=dict(colors=category_colors),
            textinfo='label+value',
        )])
        fig.update_layout(title="Overall Risk of Bias Distribution")
    else:
        fig = go.Figure(data=[go.Bar(
            x=categories,
            y=values,
            marker_color=category_colors,
            text=values,
            textposition='auto',
        )])
        fig.update_layout(
            title="Overall Risk of Bias Distribution",
            xaxis_title="Judgment",
            yaxis_title="Number of Studies",
        )

    return fig

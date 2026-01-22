"""Export functions for Risk of Bias assessments.

Provides export functionality for CSV, Excel, DOCX, and RevMan formats.
"""

import io
import json
from typing import Optional
import pandas as pd
from datetime import datetime

from core.storage.models import StudyRoBAssessment, Study, JudgmentLevel
from core.risk_of_bias.visualization import JUDGMENT_LABELS, create_summary_table


def export_to_csv(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
    include_signaling_questions: bool = False,
) -> str:
    """
    Export RoB assessments to CSV format.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies for metadata
        include_signaling_questions: Whether to include signaling question responses

    Returns:
        CSV string
    """
    df = create_summary_table(assessments, studies)

    if include_signaling_questions:
        # Add detailed signaling question columns
        sq_data = []
        for assessment in assessments:
            row = {"study_id": assessment.study_id}
            for dj in assessment.domain_judgments:
                for sr in dj.signaling_responses:
                    col_name = f"{dj.domain_name}_{sr.question_id[:8]}"
                    row[col_name] = sr.response
                    if sr.supporting_quote:
                        row[f"{col_name}_quote"] = sr.supporting_quote
            sq_data.append(row)

        sq_df = pd.DataFrame(sq_data)
        df = df.merge(sq_df, left_on="Study ID", right_on="study_id", how="left")
        if "study_id" in df.columns:
            df = df.drop(columns=["study_id"])

    return df.to_csv(index=False)


def export_to_excel(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
) -> io.BytesIO:
    """
    Export RoB assessments to Excel format with multiple sheets.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies for metadata

    Returns:
        BytesIO buffer containing Excel file
    """
    buffer = io.BytesIO()

    study_map = {}
    if studies:
        study_map = {s.id: s for s in studies}

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Summary sheet
        summary_df = create_summary_table(assessments, studies)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

        # Detailed assessments sheet
        detailed_rows = []
        for assessment in assessments:
            study = study_map.get(assessment.study_id)

            for dj in assessment.domain_judgments:
                row = {
                    "Study ID": assessment.study_id,
                    "Study Title": study.title if study else "",
                    "Authors": study.authors if study else "",
                    "Year": study.year if study else "",
                    "Tool": assessment.tool_type.value,
                    "Domain": dj.domain_name,
                    "Judgment": JUDGMENT_LABELS.get(dj.judgment, dj.judgment.value),
                    "Rationale": dj.rationale,
                    "AI Confidence": dj.ai_confidence,
                    "Human Verified": dj.is_human_verified,
                    "Flagged": dj.is_flagged_uncertain,
                    "Supporting Quotes": "; ".join(dj.supporting_quotes),
                }
                detailed_rows.append(row)

        detailed_df = pd.DataFrame(detailed_rows)
        detailed_df.to_excel(writer, sheet_name='Domain Details', index=False)

        # Signaling questions sheet
        sq_rows = []
        for assessment in assessments:
            study = study_map.get(assessment.study_id)

            for dj in assessment.domain_judgments:
                for sr in dj.signaling_responses:
                    row = {
                        "Study ID": assessment.study_id,
                        "Study Title": study.title[:50] if study else "",
                        "Domain": dj.domain_name,
                        "Question ID": sr.question_id,
                        "Response": sr.response,
                        "Supporting Quote": sr.supporting_quote or "",
                        "Notes": sr.notes or "",
                    }
                    sq_rows.append(row)

        sq_df = pd.DataFrame(sq_rows)
        sq_df.to_excel(writer, sheet_name='Signaling Questions', index=False)

        # Statistics sheet
        stats_data = []

        # Overall distribution
        overall_dist = {}
        for a in assessments:
            label = JUDGMENT_LABELS.get(a.overall_judgment, a.overall_judgment.value)
            overall_dist[label] = overall_dist.get(label, 0) + 1

        for judgment, count in overall_dist.items():
            stats_data.append({
                "Category": "Overall Judgment",
                "Value": judgment,
                "Count": count,
                "Percentage": f"{count / len(assessments) * 100:.1f}%"
            })

        stats_df = pd.DataFrame(stats_data)
        stats_df.to_excel(writer, sheet_name='Statistics', index=False)

    buffer.seek(0)
    return buffer


def export_to_json(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
) -> str:
    """
    Export RoB assessments to JSON format.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies for metadata

    Returns:
        JSON string
    """
    study_map = {}
    if studies:
        study_map = {s.id: s for s in studies}

    data = {
        "export_date": datetime.now().isoformat(),
        "total_assessments": len(assessments),
        "assessments": []
    }

    for assessment in assessments:
        study = study_map.get(assessment.study_id)

        assessment_data = {
            "id": assessment.id,
            "study_id": assessment.study_id,
            "study_info": {
                "title": study.title if study else None,
                "authors": study.authors if study else None,
                "year": study.year if study else None,
            },
            "tool_type": assessment.tool_type.value,
            "overall_judgment": assessment.overall_judgment.value,
            "overall_rationale": assessment.overall_rationale,
            "status": assessment.assessment_status,
            "domain_judgments": [
                {
                    "domain_id": dj.domain_id,
                    "domain_name": dj.domain_name,
                    "judgment": dj.judgment.value,
                    "rationale": dj.rationale,
                    "ai_confidence": dj.ai_confidence,
                    "is_human_verified": dj.is_human_verified,
                    "is_flagged": dj.is_flagged_uncertain,
                    "supporting_quotes": dj.supporting_quotes,
                    "signaling_responses": [
                        {
                            "question_id": sr.question_id,
                            "response": sr.response,
                            "supporting_quote": sr.supporting_quote,
                            "notes": sr.notes,
                        }
                        for sr in dj.signaling_responses
                    ]
                }
                for dj in assessment.domain_judgments
            ],
            "created_at": assessment.created_at.isoformat(),
            "updated_at": assessment.updated_at.isoformat(),
        }
        data["assessments"].append(assessment_data)

    return json.dumps(data, indent=2)


def export_to_revman(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
) -> str:
    """
    Export RoB assessments to RevMan XML format.

    This creates a simplified XML format compatible with Cochrane RevMan
    for import of risk of bias data.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies for metadata

    Returns:
        XML string
    """
    study_map = {}
    if studies:
        study_map = {s.id: s for s in studies}

    # Map judgment levels to RevMan format
    revman_judgment = {
        JudgmentLevel.LOW: "L",
        JudgmentLevel.SOME_CONCERNS: "U",
        JudgmentLevel.MODERATE: "U",
        JudgmentLevel.HIGH: "H",
        JudgmentLevel.SERIOUS: "H",
        JudgmentLevel.CRITICAL: "H",
        JudgmentLevel.UNCLEAR: "U",
    }

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<RISK_OF_BIAS>',
        f'  <EXPORT_DATE>{datetime.now().isoformat()}</EXPORT_DATE>',
    ]

    for assessment in assessments:
        study = study_map.get(assessment.study_id)
        study_name = study.title if study else assessment.study_id

        xml_lines.append(f'  <STUDY ID="{assessment.study_id}">')
        xml_lines.append(f'    <NAME>{_escape_xml(study_name)}</NAME>')

        for dj in assessment.domain_judgments:
            judgment_code = revman_judgment.get(dj.judgment, "U")
            xml_lines.append(f'    <ITEM DOMAIN="{_escape_xml(dj.domain_name)}">')
            xml_lines.append(f'      <JUDGMENT>{judgment_code}</JUDGMENT>')
            xml_lines.append(f'      <DESCRIPTION>{_escape_xml(dj.rationale)}</DESCRIPTION>')
            xml_lines.append('    </ITEM>')

        xml_lines.append('  </STUDY>')

    xml_lines.append('</RISK_OF_BIAS>')

    return '\n'.join(xml_lines)


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    if not text:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def import_from_csv(
    csv_content: str,
    tool_type: str,
) -> list[dict]:
    """
    Import RoB assessments from CSV format.

    Args:
        csv_content: CSV string content
        tool_type: Tool type for the assessments

    Returns:
        List of assessment dictionaries ready for processing
    """
    df = pd.read_csv(io.StringIO(csv_content))

    # Expected columns: study_id, domain_name, judgment, rationale
    required_cols = ['study_id', 'domain_name', 'judgment']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Group by study
    assessments = []
    for study_id, group in df.groupby('study_id'):
        domain_judgments = []
        for _, row in group.iterrows():
            domain_judgments.append({
                "domain_name": row['domain_name'],
                "judgment": row['judgment'],
                "rationale": row.get('rationale', ''),
                "supporting_quotes": row.get('supporting_quotes', '').split(';') if 'supporting_quotes' in row else [],
            })

        assessments.append({
            "study_id": study_id,
            "tool_type": tool_type,
            "domain_judgments": domain_judgments,
        })

    return assessments


def create_traffic_light_image(
    assessments: list[StudyRoBAssessment],
    studies: Optional[list[Study]] = None,
    format: str = "png",
) -> bytes:
    """
    Create a traffic light plot image.

    Args:
        assessments: List of RoB assessments
        studies: Optional list of studies for labels
        format: Image format (png, svg, pdf)

    Returns:
        Image bytes
    """
    from core.risk_of_bias.visualization import TrafficLightPlot

    plot = TrafficLightPlot(assessments, studies)

    try:
        fig = plot.create_matplotlib_figure()
        buffer = io.BytesIO()
        fig.savefig(buffer, format=format, bbox_inches='tight', dpi=300)
        buffer.seek(0)
        return buffer.getvalue()
    except ImportError:
        # Try plotly if matplotlib not available
        fig = plot.create_plotly_figure()
        return fig.to_image(format=format)

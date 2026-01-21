"""LLM-assisted field recommendation for data extraction."""

import json
from typing import Optional

from ..llm.base_client import BaseLLMClient
from ..llm.prompts import FIELD_RECOMMENDATION_SYSTEM, FIELD_RECOMMENDATION_USER
from ..llm.cost_tracker import CostTracker, OperationType
from ..storage.models import ExtractionField, FieldType
from ..storage.audit_logger import AuditLogger


# Default extraction fields for common systematic review types
DEFAULT_FIELDS = {
    "study_characteristics": [
        ExtractionField(
            field_name="first_author",
            description="First author's last name",
            field_type=FieldType.TEXT,
            category="study_characteristics",
            required=True,
            display_order=1,
        ),
        ExtractionField(
            field_name="publication_year",
            description="Year of publication",
            field_type=FieldType.NUMERIC,
            category="study_characteristics",
            required=True,
            display_order=2,
        ),
        ExtractionField(
            field_name="country",
            description="Country where study was conducted",
            field_type=FieldType.TEXT,
            category="study_characteristics",
            display_order=3,
        ),
        ExtractionField(
            field_name="study_design",
            description="Study design (e.g., RCT, cohort, case-control)",
            field_type=FieldType.CATEGORICAL,
            category="study_characteristics",
            required=True,
            display_order=4,
            options=["RCT", "Cohort", "Case-control", "Cross-sectional", "Case series", "Other"],
        ),
        ExtractionField(
            field_name="setting",
            description="Study setting (e.g., hospital, community, primary care)",
            field_type=FieldType.TEXT,
            category="study_characteristics",
            display_order=5,
        ),
    ],
    "population": [
        ExtractionField(
            field_name="sample_size",
            description="Total number of participants",
            field_type=FieldType.NUMERIC,
            category="population",
            required=True,
            display_order=10,
        ),
        ExtractionField(
            field_name="mean_age",
            description="Mean age of participants (years)",
            field_type=FieldType.NUMERIC,
            category="population",
            display_order=11,
        ),
        ExtractionField(
            field_name="percent_female",
            description="Percentage of female participants",
            field_type=FieldType.NUMERIC,
            category="population",
            display_order=12,
        ),
        ExtractionField(
            field_name="inclusion_criteria_study",
            description="Study's inclusion criteria",
            field_type=FieldType.TEXT,
            category="population",
            display_order=13,
        ),
    ],
    "intervention": [
        ExtractionField(
            field_name="intervention_type",
            description="Type of intervention",
            field_type=FieldType.TEXT,
            category="intervention",
            required=True,
            display_order=20,
        ),
        ExtractionField(
            field_name="intervention_details",
            description="Details of intervention (dose, duration, frequency)",
            field_type=FieldType.TEXT,
            category="intervention",
            display_order=21,
        ),
        ExtractionField(
            field_name="comparator",
            description="Comparator or control condition",
            field_type=FieldType.TEXT,
            category="intervention",
            display_order=22,
        ),
        ExtractionField(
            field_name="follow_up_duration",
            description="Duration of follow-up",
            field_type=FieldType.TEXT,
            category="intervention",
            display_order=23,
        ),
    ],
    "outcomes": [
        ExtractionField(
            field_name="primary_outcome",
            description="Primary outcome measure",
            field_type=FieldType.TEXT,
            category="outcomes",
            required=True,
            display_order=30,
        ),
        ExtractionField(
            field_name="outcome_measurement",
            description="How outcome was measured (instrument/method)",
            field_type=FieldType.TEXT,
            category="outcomes",
            display_order=31,
        ),
        ExtractionField(
            field_name="timepoint",
            description="Timepoint(s) of outcome assessment",
            field_type=FieldType.TEXT,
            category="outcomes",
            display_order=32,
        ),
    ],
    "results": [
        ExtractionField(
            field_name="effect_estimate",
            description="Main effect estimate (e.g., OR, RR, MD)",
            field_type=FieldType.TEXT,
            category="results",
            required=True,
            display_order=40,
        ),
        ExtractionField(
            field_name="confidence_interval",
            description="95% confidence interval",
            field_type=FieldType.TEXT,
            category="results",
            display_order=41,
        ),
        ExtractionField(
            field_name="p_value",
            description="P-value for main effect",
            field_type=FieldType.TEXT,
            category="results",
            display_order=42,
        ),
        ExtractionField(
            field_name="intervention_n",
            description="Sample size in intervention group",
            field_type=FieldType.NUMERIC,
            category="results",
            display_order=43,
        ),
        ExtractionField(
            field_name="control_n",
            description="Sample size in control group",
            field_type=FieldType.NUMERIC,
            category="results",
            display_order=44,
        ),
        ExtractionField(
            field_name="intervention_events",
            description="Number of events in intervention group",
            field_type=FieldType.NUMERIC,
            category="results",
            display_order=45,
        ),
        ExtractionField(
            field_name="control_events",
            description="Number of events in control group",
            field_type=FieldType.NUMERIC,
            category="results",
            display_order=46,
        ),
    ],
}


class FieldRecommender:
    """Recommend extraction fields based on research question."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize field recommender.

        Args:
            llm_client: LLM client for generating recommendations
            cost_tracker: Optional cost tracker
            audit_logger: Optional audit logger
            project_id: Optional project ID for logging
        """
        self.llm_client = llm_client
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.project_id = project_id

    def get_default_fields(self) -> list[ExtractionField]:
        """
        Get all default extraction fields.

        Returns:
            List of default ExtractionField objects
        """
        all_fields = []
        for category_fields in DEFAULT_FIELDS.values():
            all_fields.extend(category_fields)
        return sorted(all_fields, key=lambda f: f.display_order)

    def recommend_fields(
        self,
        research_question: str,
        study_types: Optional[list[str]] = None,
    ) -> list[ExtractionField]:
        """
        Recommend extraction fields based on research question.

        Args:
            research_question: The systematic review research question
            study_types: List of included study types (e.g., ["RCT", "Cohort"])

        Returns:
            List of recommended ExtractionField objects
        """
        study_types_str = ", ".join(study_types) if study_types else "Various study types"

        # Build prompt
        prompt = FIELD_RECOMMENDATION_USER.format(
            research_question=research_question,
            study_types=study_types_str,
        )

        messages = [
            {"role": "system", "content": FIELD_RECOMMENDATION_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        # Call LLM
        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
            json_mode=True,
        )

        # Parse response
        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Return default fields if parsing fails
                return self.get_default_fields()

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.FIELD_RECOMMENDATION,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        # Log to audit trail
        if self.audit_logger and self.project_id:
            self.audit_logger.log_llm_call(
                project_id=self.project_id,
                operation="field_recommendation",
                prompt=prompt,
                response=response.content,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        # Build ExtractionField objects from response
        fields = []
        recommended = data.get("recommended_fields", [])

        for i, field_data in enumerate(recommended):
            # Map field type
            field_type_str = field_data.get("field_type", "text").lower()
            try:
                field_type = FieldType(field_type_str)
            except ValueError:
                field_type = FieldType.TEXT

            field = ExtractionField(
                field_name=field_data.get("field_name", f"field_{i}"),
                description=field_data.get("description", ""),
                field_type=field_type,
                category=field_data.get("category", "other"),
                required=field_data.get("required", False),
                display_order=i * 10,
            )
            fields.append(field)

        return fields

    def merge_with_defaults(
        self,
        recommended_fields: list[ExtractionField],
        include_defaults: bool = True,
    ) -> list[ExtractionField]:
        """
        Merge recommended fields with default fields.

        Args:
            recommended_fields: LLM-recommended fields
            include_defaults: Whether to include default fields

        Returns:
            Combined list of fields, deduplicated
        """
        if not include_defaults:
            return recommended_fields

        # Start with defaults
        all_fields = {f.field_name: f for f in self.get_default_fields()}

        # Add/override with recommended
        for field in recommended_fields:
            all_fields[field.field_name] = field

        return sorted(all_fields.values(), key=lambda f: f.display_order)

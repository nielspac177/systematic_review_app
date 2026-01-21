"""Data extraction from full-text PDFs using LLM."""

import json
from typing import Optional, Callable
import pandas as pd

from ..llm.base_client import BaseLLMClient
from ..llm.prompts import DATA_EXTRACTION_SYSTEM, DATA_EXTRACTION_USER
from ..llm.cost_tracker import CostTracker, OperationType, BudgetExceededError
from ..storage.models import (
    Study, ExtractionField, ExtractedValue, StudyExtraction
)
from ..storage.audit_logger import AuditLogger


class DataExtractor:
    """Extract structured data from study full-texts."""

    # Maximum characters to send to LLM
    MAX_TEXT_CHARS = 50000

    def __init__(
        self,
        llm_client: BaseLLMClient,
        fields: list[ExtractionField],
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize data extractor.

        Args:
            llm_client: LLM client for extraction
            fields: List of fields to extract
            cost_tracker: Optional cost tracker
            audit_logger: Optional audit logger
            project_id: Optional project ID for logging
        """
        self.llm_client = llm_client
        self.fields = fields
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.project_id = project_id

    def _build_fields_description(self) -> str:
        """Build formatted description of fields to extract."""
        lines = []
        for field in self.fields:
            line = f"- {field.field_name}: {field.description}"
            if field.field_type.value == "numeric":
                line += " (extract numeric value only)"
            elif field.field_type.value == "categorical" and field.options:
                line += f" (options: {', '.join(field.options)})"
            lines.append(line)
        return "\n".join(lines)

    def _truncate_text(self, text: str) -> str:
        """Truncate text to fit within context limits."""
        if len(text) <= self.MAX_TEXT_CHARS:
            return text

        # Keep beginning and end for context
        half = self.MAX_TEXT_CHARS // 2
        return text[:half] + "\n\n[...text truncated...]\n\n" + text[-half:]

    def estimate_cost(self, n_studies: int, avg_text_length: int = 20000) -> float:
        """
        Estimate cost for extracting data from N studies.

        Args:
            n_studies: Number of studies
            avg_text_length: Average text length in characters

        Returns:
            Estimated cost in USD
        """
        avg_input_tokens = min(avg_text_length // 4, self.MAX_TEXT_CHARS // 4) + 500
        avg_output_tokens = 50 * len(self.fields)  # ~50 tokens per field

        if self.cost_tracker:
            estimate = self.cost_tracker.estimate_cost(
                llm_client=self.llm_client,
                operation=OperationType.DATA_EXTRACTION,
                n_items=n_studies,
                avg_input_tokens=avg_input_tokens,
                avg_output_tokens=avg_output_tokens,
            )
            return estimate.estimated_cost

        return self.llm_client.estimate_cost(
            avg_input_tokens * n_studies,
            avg_output_tokens * n_studies
        )

    def extract_from_study(self, study: Study) -> StudyExtraction:
        """
        Extract data from a single study.

        Args:
            study: Study with pdf_text populated

        Returns:
            StudyExtraction with extracted values
        """
        if not study.pdf_text:
            # Return empty extraction with all fields as NR
            extractions = {}
            for field in self.fields:
                extractions[field.field_name] = ExtractedValue(
                    field_name=field.field_name,
                    value=None,
                    is_not_reported=True,
                    notes="Full text not available",
                    source="llm",
                )
            return StudyExtraction(
                study_id=study.id,
                extractions=extractions,
                extraction_quality={
                    "completeness": 0.0,
                    "fields_not_reported": [f.field_name for f in self.fields],
                    "notes": "Full text not available",
                },
            )

        # Build prompt
        fields_desc = self._build_fields_description()
        text = self._truncate_text(study.pdf_text)

        prompt = DATA_EXTRACTION_USER.format(
            fields_with_descriptions=fields_desc,
            pdf_text=text,
        )

        messages = [
            {"role": "system", "content": DATA_EXTRACTION_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        # Call LLM
        response = self.llm_client.chat(
            messages=messages,
            temperature=0.2,  # Low temperature for accurate extraction
            max_tokens=2000,
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
                data = {"extractions": {}, "extraction_quality": None}

        # Build ExtractedValue objects
        extractions = {}
        llm_extractions = data.get("extractions", {})

        for field in self.fields:
            field_data = llm_extractions.get(field.field_name, {})

            if isinstance(field_data, dict):
                value = field_data.get("value")
                source_quote = field_data.get("source_quote")
                notes = field_data.get("notes")
            else:
                # Handle case where LLM returns simple value instead of dict
                value = field_data
                source_quote = None
                notes = None

            # Check if not reported
            is_nr = value is None or str(value).upper() in ["NR", "NOT REPORTED", "N/A", ""]

            extractions[field.field_name] = ExtractedValue(
                field_name=field.field_name,
                value=None if is_nr else str(value),
                is_not_reported=is_nr,
                source_quote=source_quote,
                notes=notes,
                source="llm",
            )

        # Get extraction quality
        quality = data.get("extraction_quality", {})
        if not quality:
            nr_count = sum(1 for e in extractions.values() if e.is_not_reported)
            quality = {
                "completeness": 1 - (nr_count / len(self.fields)) if self.fields else 1,
                "fields_not_reported": [
                    f for f, e in extractions.items() if e.is_not_reported
                ],
            }

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.DATA_EXTRACTION,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                study_id=study.id,
                model=response.model,
            )

        # Log to audit trail
        if self.audit_logger and self.project_id:
            self.audit_logger.log_llm_call(
                project_id=self.project_id,
                study_id=study.id,
                operation="data_extraction",
                prompt=prompt[:5000] + "..." if len(prompt) > 5000 else prompt,
                response=response.content,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        return StudyExtraction(
            study_id=study.id,
            extractions=extractions,
            extraction_quality=quality,
        )

    def extract_batch(
        self,
        studies: list[Study],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        stop_on_budget: bool = True,
    ) -> tuple[list[StudyExtraction], bool]:
        """
        Extract data from multiple studies.

        Args:
            studies: List of studies to process
            progress_callback: Optional progress callback
            stop_on_budget: If True, stop when budget exceeded

        Returns:
            Tuple of (list of extractions, completed flag)
        """
        extractions = []
        total = len(studies)

        for i, study in enumerate(studies):
            if progress_callback:
                progress_callback(i, total, f"Extracting: {study.title[:40]}...")

            try:
                extraction = self.extract_from_study(study)
                extractions.append(extraction)
            except BudgetExceededError:
                if stop_on_budget:
                    if progress_callback:
                        progress_callback(i, total, "Stopped: Budget limit exceeded")
                    return extractions, False
                raise

        if progress_callback:
            progress_callback(total, total, "Extraction complete")

        return extractions, True

    def to_dataframe(self, extractions: list[StudyExtraction]) -> pd.DataFrame:
        """
        Convert extractions to a DataFrame.

        Args:
            extractions: List of StudyExtraction objects

        Returns:
            DataFrame with one row per study, one column per field
        """
        rows = []
        for ext in extractions:
            row = {"study_id": ext.study_id}
            for field_name, value in ext.extractions.items():
                row[field_name] = value.value if not value.is_not_reported else "NR"
                row[f"{field_name}_nr"] = value.is_not_reported
            rows.append(row)

        df = pd.DataFrame(rows)

        # Reorder columns: study_id first, then fields in order
        field_names = [f.field_name for f in self.fields]
        ordered_cols = ["study_id"]
        for fn in field_names:
            if fn in df.columns:
                ordered_cols.append(fn)
            if f"{fn}_nr" in df.columns:
                ordered_cols.append(f"{fn}_nr")

        # Add any remaining columns
        for col in df.columns:
            if col not in ordered_cols:
                ordered_cols.append(col)

        return df[ordered_cols]

    def get_statistics(self, extractions: list[StudyExtraction]) -> dict:
        """
        Get extraction statistics.

        Args:
            extractions: List of extractions

        Returns:
            Dictionary with statistics
        """
        total_fields = len(self.fields) * len(extractions)
        nr_count = 0
        field_nr_counts = {f.field_name: 0 for f in self.fields}

        for ext in extractions:
            for field_name, value in ext.extractions.items():
                if value.is_not_reported:
                    nr_count += 1
                    if field_name in field_nr_counts:
                        field_nr_counts[field_name] += 1

        return {
            "total_studies": len(extractions),
            "total_fields": total_fields,
            "fields_extracted": total_fields - nr_count,
            "fields_not_reported": nr_count,
            "completeness_rate": (total_fields - nr_count) / total_fields if total_fields > 0 else 0,
            "nr_by_field": field_nr_counts,
            "most_missing_fields": sorted(
                field_nr_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
        }

"""PICO analysis using LLM for research question breakdown."""

import json
from typing import Optional

from ..storage.models import PICOElement, ConceptBlock
from ..llm.cost_tracker import CostTracker, OperationType
from ..storage.audit_logger import AuditLogger
from .search_prompts import PICO_ANALYSIS_SYSTEM, PICO_ANALYSIS_USER


class PICOAnalyzer:
    """Analyze research questions and extract PICO elements with search terms."""

    def __init__(
        self,
        llm_client,
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize PICO analyzer.

        Args:
            llm_client: LLM client for analysis
            cost_tracker: Optional cost tracker for API call tracking
            audit_logger: Optional audit logger for transparency
            project_id: Optional project ID for logging
        """
        self.llm_client = llm_client
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.project_id = project_id

    def analyze(self, research_question: str) -> dict:
        """
        Analyze a research question and extract PICO elements.

        Args:
            research_question: The research question to analyze

        Returns:
            Dictionary with PICO analysis including elements, terms, and notes
        """
        prompt = PICO_ANALYSIS_USER.format(research_question=research_question)

        messages = [
            {"role": "system", "content": PICO_ANALYSIS_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
            json_mode=True,
        )

        # Parse response
        try:
            analysis = json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                raise ValueError("Failed to parse PICO analysis response")

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.PICO_ANALYSIS,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
                notes=f"PICO analysis for: {research_question[:50]}...",
            )

        # Log audit trail
        if self.audit_logger and self.project_id:
            self.audit_logger.log_operation(
                project_id=self.project_id,
                operation="pico_analysis",
                prompt=prompt,
                response=response.content,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        return analysis

    def create_concept_blocks(self, pico_analysis: dict) -> list[ConceptBlock]:
        """
        Create concept blocks from PICO analysis.

        Args:
            pico_analysis: PICO analysis dictionary from analyze()

        Returns:
            List of ConceptBlock objects
        """
        concept_blocks = []

        # Create blocks for main PICO elements
        pico_mapping = [
            ("population", "population"),
            ("intervention", "intervention"),
            ("comparison", "comparison"),
            ("outcome", "outcome"),
        ]

        for key, element_type in pico_mapping:
            if key in pico_analysis and pico_analysis[key]:
                element_data = pico_analysis[key]

                pico_element = PICOElement(
                    element_type=element_type,
                    label=element_data.get("label", key.capitalize()),
                    primary_terms=element_data.get("primary_terms", []),
                    synonyms=element_data.get("synonyms", []),
                    mesh_terms=element_data.get("mesh_terms", []),
                    notes=element_data.get("notes", ""),
                )

                concept_block = ConceptBlock(
                    name=f"{key.capitalize()} Concept",
                    pico_element=pico_element,
                )
                concept_blocks.append(concept_block)

        # Add other concepts if present
        if "other_concepts" in pico_analysis:
            for i, concept in enumerate(pico_analysis["other_concepts"]):
                pico_element = PICOElement(
                    element_type="other",
                    label=concept.get("label", f"Other Concept {i+1}"),
                    primary_terms=concept.get("primary_terms", []),
                    synonyms=concept.get("synonyms", []),
                    mesh_terms=concept.get("mesh_terms", []),
                    notes=concept.get("notes", ""),
                )

                concept_block = ConceptBlock(
                    name=concept.get("label", f"Other Concept {i+1}"),
                    pico_element=pico_element,
                )
                concept_blocks.append(concept_block)

        return concept_blocks

    def suggest_additional_terms(
        self,
        concept_label: str,
        current_terms: list[str],
    ) -> dict:
        """
        Suggest additional search terms for a concept.

        Args:
            concept_label: Description of the concept
            current_terms: Currently selected terms

        Returns:
            Dictionary with suggested terms
        """
        from .search_prompts import TERM_SUGGESTION_SYSTEM, TERM_SUGGESTION_USER

        prompt = TERM_SUGGESTION_USER.format(
            concept_label=concept_label,
            current_terms=", ".join(current_terms),
        )

        messages = [
            {"role": "system", "content": TERM_SUGGESTION_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=500,
            json_mode=True,
        )

        try:
            suggestions = json.loads(response.content)
        except json.JSONDecodeError:
            suggestions = {"suggested_synonyms": [], "suggested_mesh_terms": []}

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.PICO_ANALYSIS,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
                notes=f"Term suggestions for: {concept_label[:30]}...",
            )

        return suggestions

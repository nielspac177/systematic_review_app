"""LLM-assisted criteria generation for systematic reviews."""

import json
from typing import Optional

from ..llm.base_client import BaseLLMClient, LLMResponse
from ..llm.prompts import CRITERIA_GENERATION_SYSTEM, CRITERIA_GENERATION_USER
from ..llm.cost_tracker import CostTracker, OperationType
from ..storage.models import ReviewCriteria, InclusionCriteria
from ..storage.audit_logger import AuditLogger


class CriteriaGenerator:
    """Generate inclusion/exclusion criteria using LLM."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize criteria generator.

        Args:
            llm_client: LLM client for generating criteria
            cost_tracker: Optional cost tracker
            audit_logger: Optional audit logger
            project_id: Optional project ID for logging
        """
        self.llm_client = llm_client
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.project_id = project_id

    def generate_criteria(self, research_question: str) -> ReviewCriteria:
        """
        Generate inclusion/exclusion criteria from research question.

        Args:
            research_question: The systematic review research question

        Returns:
            ReviewCriteria with generated criteria
        """
        # Build messages
        messages = [
            {"role": "system", "content": CRITERIA_GENERATION_SYSTEM},
            {"role": "user", "content": CRITERIA_GENERATION_USER.format(
                research_question=research_question
            )}
        ]

        # Call LLM
        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
            json_mode=True,
        )

        # Parse response
        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"Failed to parse LLM response as JSON: {response.content}")

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.CRITERIA_GENERATION,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        # Log to audit trail
        if self.audit_logger and self.project_id:
            self.audit_logger.log_llm_call(
                project_id=self.project_id,
                operation="criteria_generation",
                prompt=messages[-1]["content"],
                response=response.content,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        # Build ReviewCriteria
        inclusion_data = data.get("inclusion_criteria", {})
        inclusion = InclusionCriteria(
            population=inclusion_data.get("population", ""),
            intervention=inclusion_data.get("intervention", ""),
            comparison=inclusion_data.get("comparison", "Not applicable"),
            outcome=inclusion_data.get("outcome", ""),
            study_design=inclusion_data.get("study_design", ""),
        )

        return ReviewCriteria(
            inclusion=inclusion,
            exclusion=data.get("exclusion_criteria", []),
            suggested_exclusion_reasons=data.get("suggested_exclusion_reasons", []),
        )

    def estimate_cost(self) -> float:
        """
        Estimate cost for criteria generation.

        Returns:
            Estimated cost in USD
        """
        if self.cost_tracker:
            estimate = self.cost_tracker.estimate_cost(
                llm_client=self.llm_client,
                operation=OperationType.CRITERIA_GENERATION,
                n_items=1,
            )
            return estimate.estimated_cost

        # Fallback estimate
        return self.llm_client.estimate_cost(200, 500)

    def refine_criteria(
        self,
        current_criteria: ReviewCriteria,
        feedback: str
    ) -> ReviewCriteria:
        """
        Refine criteria based on user feedback.

        Args:
            current_criteria: Current criteria to refine
            feedback: User feedback on what to change

        Returns:
            Updated ReviewCriteria
        """
        refine_prompt = f"""
Current inclusion criteria:
- Population: {current_criteria.inclusion.population}
- Intervention: {current_criteria.inclusion.intervention}
- Comparison: {current_criteria.inclusion.comparison}
- Outcome: {current_criteria.inclusion.outcome}
- Study Design: {current_criteria.inclusion.study_design}

Current exclusion criteria:
{chr(10).join('- ' + c for c in current_criteria.exclusion)}

User feedback for refinement:
{feedback}

Please update the criteria based on this feedback. Return the complete updated criteria.

Respond in JSON format:
{{
    "inclusion_criteria": {{
        "population": "...",
        "intervention": "...",
        "comparison": "...",
        "outcome": "...",
        "study_design": "..."
    }},
    "exclusion_criteria": ["..."],
    "suggested_exclusion_reasons": ["..."]
}}
"""

        messages = [
            {"role": "system", "content": CRITERIA_GENERATION_SYSTEM},
            {"role": "user", "content": refine_prompt}
        ]

        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
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
                raise ValueError(f"Failed to parse LLM response as JSON: {response.content}")

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.CRITERIA_GENERATION,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
                notes="criteria_refinement",
            )

        # Log to audit trail
        if self.audit_logger and self.project_id:
            self.audit_logger.log_llm_call(
                project_id=self.project_id,
                operation="criteria_refinement",
                prompt=refine_prompt,
                response=response.content,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        # Build updated criteria
        inclusion_data = data.get("inclusion_criteria", {})
        inclusion = InclusionCriteria(
            population=inclusion_data.get("population", current_criteria.inclusion.population),
            intervention=inclusion_data.get("intervention", current_criteria.inclusion.intervention),
            comparison=inclusion_data.get("comparison", current_criteria.inclusion.comparison),
            outcome=inclusion_data.get("outcome", current_criteria.inclusion.outcome),
            study_design=inclusion_data.get("study_design", current_criteria.inclusion.study_design),
        )

        return ReviewCriteria(
            inclusion=inclusion,
            exclusion=data.get("exclusion_criteria", current_criteria.exclusion),
            suggested_exclusion_reasons=data.get(
                "suggested_exclusion_reasons",
                current_criteria.suggested_exclusion_reasons
            ),
        )

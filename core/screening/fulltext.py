"""Full-text screening for systematic reviews."""

import json
from typing import Optional, Callable

from ..llm.base_client import BaseLLMClient
from ..llm.prompts import FULLTEXT_SCREENING_SYSTEM, FULLTEXT_SCREENING_USER
from ..llm.cost_tracker import CostTracker, OperationType, BudgetExceededError
from ..storage.models import (
    Study, ScreeningDecision, ReviewCriteria,
    ExclusionCategory, ScreeningPhase
)
from ..storage.audit_logger import AuditLogger


class FulltextScreener:
    """Screen studies based on full-text content."""

    # Maximum characters to send to LLM (to stay within context limits)
    MAX_TEXT_CHARS = 50000

    def __init__(
        self,
        llm_client: BaseLLMClient,
        criteria: ReviewCriteria,
        research_question: str,
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize full-text screener.

        Args:
            llm_client: LLM client for screening
            criteria: Review criteria to apply
            research_question: The research question
            cost_tracker: Optional cost tracker
            audit_logger: Optional audit logger
            project_id: Optional project ID for logging
        """
        self.llm_client = llm_client
        self.criteria = criteria
        self.research_question = research_question
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.project_id = project_id

    def estimate_cost(self, n_studies: int, avg_text_length: int = 20000) -> float:
        """
        Estimate total cost for full-text screening.

        Args:
            n_studies: Number of studies to screen
            avg_text_length: Average full-text length in characters

        Returns:
            Estimated cost in USD
        """
        # Estimate tokens from text length (rough: 4 chars per token)
        avg_input_tokens = min(avg_text_length // 4, self.MAX_TEXT_CHARS // 4) + 500  # +500 for prompt
        avg_output_tokens = 400  # Larger response with criteria evaluation

        if self.cost_tracker:
            estimate = self.cost_tracker.estimate_cost(
                llm_client=self.llm_client,
                operation=OperationType.FULLTEXT_SCREENING,
                n_items=n_studies,
                avg_input_tokens=avg_input_tokens,
                avg_output_tokens=avg_output_tokens,
            )
            return estimate.estimated_cost

        return self.llm_client.estimate_cost(
            avg_input_tokens * n_studies,
            avg_output_tokens * n_studies
        )

    def _truncate_text(self, text: str) -> str:
        """Truncate text to fit within context limits."""
        if len(text) <= self.MAX_TEXT_CHARS:
            return text

        # Keep beginning and end for context
        half = self.MAX_TEXT_CHARS // 2
        return text[:half] + "\n\n[...text truncated...]\n\n" + text[-half:]

    def screen_study(self, study: Study) -> ScreeningDecision:
        """
        Screen a single study based on full text.

        Args:
            study: Study to screen (must have pdf_text populated)

        Returns:
            ScreeningDecision with result
        """
        if not study.pdf_text:
            return ScreeningDecision(
                study_id=study.id,
                phase=ScreeningPhase.FULLTEXT,
                decision="excluded",
                reason="Full text not available for screening",
                reason_category=ExclusionCategory.NOT_ACCESSIBLE,
                confidence=1.0,
            )

        # Build exclusion criteria string
        exclusion_str = "\n".join(f"- {c}" for c in self.criteria.exclusion)

        # Truncate text if needed
        fulltext = self._truncate_text(study.pdf_text)

        # Build prompt
        prompt = FULLTEXT_SCREENING_USER.format(
            research_question=self.research_question,
            population=self.criteria.inclusion.population,
            intervention=self.criteria.inclusion.intervention,
            comparison=self.criteria.inclusion.comparison,
            outcome=self.criteria.inclusion.outcome,
            study_design=self.criteria.inclusion.study_design,
            exclusion_criteria=exclusion_str,
            fulltext=fulltext,
        )

        messages = [
            {"role": "system", "content": FULLTEXT_SCREENING_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        # Call LLM
        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=800,
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
                data = {
                    "decision": "included",
                    "reason": "Unable to parse LLM response - including for manual review",
                    "reason_category": "other",
                    "confidence": 0.5,
                    "criteria_evaluation": None,
                }

        # Map reason category
        reason_category_str = data.get("reason_category", "other").lower()
        try:
            reason_category = ExclusionCategory(reason_category_str)
        except ValueError:
            reason_category = ExclusionCategory.OTHER

        # Create decision
        decision = ScreeningDecision(
            study_id=study.id,
            phase=ScreeningPhase.FULLTEXT,
            decision=data.get("decision", "included"),
            reason=data.get("reason", ""),
            reason_category=reason_category,
            confidence=float(data.get("confidence", 0.8)),
            criteria_evaluation=data.get("criteria_evaluation"),
        )

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.FULLTEXT_SCREENING,
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
                operation="fulltext_screening",
                prompt=prompt[:5000] + "..." if len(prompt) > 5000 else prompt,  # Truncate for logging
                response=response.content,
                decision=decision.decision,
                confidence=decision.confidence,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        return decision

    def screen_batch(
        self,
        studies: list[Study],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        stop_on_budget: bool = True,
    ) -> tuple[list[ScreeningDecision], bool]:
        """
        Screen a batch of studies.

        Args:
            studies: List of studies to screen (must have pdf_text)
            progress_callback: Optional callback(current, total, status)
            stop_on_budget: If True, stop when budget exceeded

        Returns:
            Tuple of (list of decisions, completed flag)
        """
        decisions = []
        total = len(studies)

        for i, study in enumerate(studies):
            if progress_callback:
                progress_callback(i, total, f"Full-text screening: {study.title[:40]}...")

            try:
                decision = self.screen_study(study)
                decisions.append(decision)
            except BudgetExceededError:
                if stop_on_budget:
                    if progress_callback:
                        progress_callback(i, total, "Stopped: Budget limit exceeded")
                    return decisions, False
                raise

        if progress_callback:
            progress_callback(total, total, "Full-text screening complete")

        return decisions, True

    def get_statistics(self, decisions: list[ScreeningDecision]) -> dict:
        """
        Get full-text screening statistics.

        Args:
            decisions: List of screening decisions

        Returns:
            Dictionary with statistics
        """
        included = [d for d in decisions if d.decision == "included"]
        excluded = [d for d in decisions if d.decision == "excluded"]

        # Count by exclusion category
        category_counts = {}
        for d in excluded:
            cat = d.reason_category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Criteria evaluation summary
        criteria_met = {"population": 0, "intervention": 0, "comparison": 0, "outcome": 0, "study_design": 0}
        for d in included:
            if d.criteria_evaluation:
                for criterion, eval_data in d.criteria_evaluation.items():
                    if criterion in criteria_met and eval_data.get("met"):
                        criteria_met[criterion] += 1

        return {
            "total": len(decisions),
            "included": len(included),
            "excluded": len(excluded),
            "not_accessible": len([d for d in excluded if d.reason_category == ExclusionCategory.NOT_ACCESSIBLE]),
            "exclusion_by_category": category_counts,
            "criteria_met_counts": criteria_met,
        }

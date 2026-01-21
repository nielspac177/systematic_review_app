"""Feedback loop for re-reviewing low-confidence exclusions."""

import json
from typing import Optional, Callable

from ..llm.base_client import BaseLLMClient
from ..llm.prompts import FEEDBACK_REVIEW_SYSTEM, FEEDBACK_REVIEW_USER
from ..llm.cost_tracker import CostTracker, OperationType, BudgetExceededError
from ..storage.models import Study, ScreeningDecision, ReviewCriteria
from ..storage.audit_logger import AuditLogger


class FeedbackReviewer:
    """Re-review excluded studies with low confidence scores."""

    CONFIDENCE_THRESHOLD = 0.8  # Default threshold for flagging

    def __init__(
        self,
        llm_client: BaseLLMClient,
        criteria: ReviewCriteria,
        research_question: str,
        confidence_threshold: float = 0.8,
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize feedback reviewer.

        Args:
            llm_client: LLM client for reviewing
            criteria: Review criteria
            research_question: The research question
            confidence_threshold: Threshold below which to flag for review
            cost_tracker: Optional cost tracker
            audit_logger: Optional audit logger
            project_id: Optional project ID for logging
        """
        self.llm_client = llm_client
        self.criteria = criteria
        self.research_question = research_question
        self.confidence_threshold = confidence_threshold
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.project_id = project_id

    def get_studies_for_review(
        self, decisions: list[ScreeningDecision]
    ) -> list[ScreeningDecision]:
        """
        Get excluded studies that need re-review.

        Args:
            decisions: All screening decisions

        Returns:
            List of decisions with confidence below threshold
        """
        return [
            d for d in decisions
            if d.decision == "excluded"
            and d.confidence < self.confidence_threshold
            and not d.feedback_reviewed
        ]

    def estimate_cost(self, n_studies: int) -> float:
        """
        Estimate cost for feedback review.

        Args:
            n_studies: Number of studies to review

        Returns:
            Estimated cost in USD
        """
        if self.cost_tracker:
            estimate = self.cost_tracker.estimate_cost(
                llm_client=self.llm_client,
                operation=OperationType.FEEDBACK_REVIEW,
                n_items=n_studies,
            )
            return estimate.estimated_cost

        return self.llm_client.estimate_cost(600 * n_studies, 150 * n_studies)

    def review_decision(
        self,
        decision: ScreeningDecision,
        study: Study
    ) -> ScreeningDecision:
        """
        Re-review a single exclusion decision.

        Args:
            decision: The original exclusion decision
            study: The study that was excluded

        Returns:
            Updated ScreeningDecision with feedback fields populated
        """
        # Build prompt
        prompt = FEEDBACK_REVIEW_USER.format(
            reason=decision.reason,
            confidence=decision.confidence,
            research_question=self.research_question,
            population=self.criteria.inclusion.population,
            intervention=self.criteria.inclusion.intervention,
            comparison=self.criteria.inclusion.comparison,
            outcome=self.criteria.inclusion.outcome,
            study_design=self.criteria.inclusion.study_design,
            title=study.title,
            abstract=study.abstract or "Abstract not available",
        )

        messages = [
            {"role": "system", "content": FEEDBACK_REVIEW_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        # Call LLM
        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=300,
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
                    "reconsider": False,
                    "rationale": "Unable to parse LLM response",
                    "new_confidence": decision.confidence
                }

        # Update decision with feedback
        decision.feedback_reviewed = True
        decision.feedback_reconsider = data.get("reconsider", False)
        decision.feedback_rationale = data.get("rationale", "")
        decision.feedback_new_confidence = float(data.get("new_confidence", decision.confidence))

        # If reconsidering, mark for inclusion pending user confirmation
        if decision.feedback_reconsider:
            decision.feedback_final_decision = "included"
        else:
            decision.feedback_final_decision = "excluded"

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.FEEDBACK_REVIEW,
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
                operation="feedback_review",
                prompt=prompt,
                response=response.content,
                decision="reconsider" if decision.feedback_reconsider else "maintain_exclusion",
                confidence=decision.feedback_new_confidence,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        return decision

    def review_batch(
        self,
        decisions: list[ScreeningDecision],
        studies: dict[str, Study],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        stop_on_budget: bool = True,
    ) -> tuple[list[ScreeningDecision], bool]:
        """
        Re-review a batch of decisions.

        Args:
            decisions: Decisions to review
            studies: Dictionary mapping study_id to Study objects
            progress_callback: Optional progress callback
            stop_on_budget: If True, stop when budget exceeded

        Returns:
            Tuple of (updated decisions, completed flag)
        """
        total = len(decisions)

        for i, decision in enumerate(decisions):
            study = studies.get(decision.study_id)
            if not study:
                continue

            if progress_callback:
                progress_callback(i, total, f"Reviewing: {study.title[:40]}...")

            try:
                self.review_decision(decision, study)
            except BudgetExceededError:
                if stop_on_budget:
                    if progress_callback:
                        progress_callback(i, total, "Stopped: Budget limit exceeded")
                    return decisions, False
                raise

        if progress_callback:
            progress_callback(total, total, "Feedback review complete")

        return decisions, True

    def apply_user_overrides(
        self,
        decisions: list[ScreeningDecision],
        overrides: dict[str, str]
    ) -> list[ScreeningDecision]:
        """
        Apply user overrides to feedback decisions.

        Args:
            decisions: Decisions with feedback
            overrides: Dictionary mapping study_id to final decision ("included"/"excluded")

        Returns:
            Updated decisions
        """
        for decision in decisions:
            if decision.study_id in overrides:
                decision.feedback_final_decision = overrides[decision.study_id]

        return decisions

    def get_statistics(self, decisions: list[ScreeningDecision]) -> dict:
        """
        Get feedback review statistics.

        Args:
            decisions: Decisions that have been reviewed

        Returns:
            Dictionary with statistics
        """
        reviewed = [d for d in decisions if d.feedback_reviewed]
        reconsidered = [d for d in reviewed if d.feedback_reconsider]

        # Count final decisions
        final_included = [d for d in reviewed if d.feedback_final_decision == "included"]
        final_excluded = [d for d in reviewed if d.feedback_final_decision == "excluded"]

        return {
            "total_flagged": len(decisions),
            "total_reviewed": len(reviewed),
            "llm_reconsidered": len(reconsidered),
            "final_included": len(final_included),
            "final_excluded": len(final_excluded),
            "reconsideration_rate": len(reconsidered) / len(reviewed) if reviewed else 0,
        }

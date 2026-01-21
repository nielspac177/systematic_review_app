"""Title and abstract screening for systematic reviews."""

import os
import json
import logging
import hashlib
from typing import Optional, Callable
import pandas as pd

from ..llm.base_client import BaseLLMClient
from ..llm.cost_tracker import CostTracker, OperationType, BudgetExceededError
from ..storage.models import (
    Study, ScreeningDecision, ReviewCriteria,
    ExclusionCategory, ScreeningPhase
)
from ..storage.audit_logger import AuditLogger

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Maximum abstract length in characters (configurable via env var)
MAX_ABSTRACT_CHARS = int(os.getenv("SCREENING_MAX_ABSTRACT_CHARS", "2000"))

# Maximum title length in characters
MAX_TITLE_CHARS = int(os.getenv("SCREENING_MAX_TITLE_CHARS", "300"))


# =============================================================================
# COMPACT PROMPTS (reduces tokens per request)
# =============================================================================

COMPACT_SYSTEM_PROMPT = """You are a systematic review screener. Evaluate studies against PICO criteria. Be thorough but inclusive - when uncertain, include for full-text review. Respond only in JSON."""

COMPACT_USER_PROMPT_TEMPLATE = """Evaluate this study for inclusion.

Research Question: {research_question}

PICO Criteria:
P: {population}
I: {intervention}
C: {comparison}
O: {outcome}
Design: {study_design}

Exclusion criteria: {exclusion_criteria}

Study:
Title: {title}
Abstract: {abstract}

Respond in JSON:
{{"decision":"included"/"excluded","reason":"brief explanation","reason_category":"wrong_population/wrong_intervention/wrong_comparator/wrong_outcome/wrong_study_design/other/meets_criteria","confidence":0.0-1.0}}"""


def truncate_text(text: str, max_chars: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum number of characters.

    Args:
        text: Text to truncate
        max_chars: Maximum characters
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if not text or len(text) <= max_chars:
        return text

    # Truncate and try to end at a word boundary
    truncated = text[:max_chars - len(suffix)]
    last_space = truncated.rfind(' ')
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]

    return truncated + suffix


def get_study_hash(study: Study) -> str:
    """
    Generate a hash for a study to use as a cache key.

    Args:
        study: Study object

    Returns:
        Hash string
    """
    content = f"{study.title}|{study.abstract or ''}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class TitleAbstractScreener:
    """Screen studies based on title and abstract with rate limiting support."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        criteria: ReviewCriteria,
        research_question: str,
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        project_id: Optional[str] = None,
        max_abstract_chars: int = MAX_ABSTRACT_CHARS,
        max_title_chars: int = MAX_TITLE_CHARS,
    ):
        """
        Initialize title/abstract screener.

        Args:
            llm_client: LLM client for screening
            criteria: Review criteria to apply
            research_question: The research question
            cost_tracker: Optional cost tracker
            audit_logger: Optional audit logger
            project_id: Optional project ID for logging
            max_abstract_chars: Maximum abstract length
            max_title_chars: Maximum title length
        """
        self.llm_client = llm_client
        self.criteria = criteria
        self.research_question = research_question
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.project_id = project_id
        self.max_abstract_chars = max_abstract_chars
        self.max_title_chars = max_title_chars

        # Cache for screening decisions (prevents duplicate API calls)
        self._decision_cache: dict[str, ScreeningDecision] = {}

        # Build compact exclusion criteria string once
        self._exclusion_str = "; ".join(self.criteria.exclusion) if self.criteria.exclusion else "None specified"

    def estimate_cost(self, n_studies: int) -> float:
        """
        Estimate total cost for screening N studies.

        Args:
            n_studies: Number of studies to screen

        Returns:
            Estimated cost in USD
        """
        if self.cost_tracker:
            estimate = self.cost_tracker.estimate_cost(
                llm_client=self.llm_client,
                operation=OperationType.TITLE_ABSTRACT_SCREENING,
                n_items=n_studies,
            )
            return estimate.estimated_cost

        # Fallback estimate
        avg_input_tokens = 400  # Reduced due to compact prompts
        avg_output_tokens = 80
        return self.llm_client.estimate_cost(
            avg_input_tokens * n_studies,
            avg_output_tokens * n_studies
        )

    def _build_prompt(self, study: Study) -> str:
        """
        Build the screening prompt for a study.

        Args:
            study: Study to screen

        Returns:
            Formatted prompt string
        """
        # Truncate title and abstract
        title = truncate_text(study.title, self.max_title_chars)
        abstract = truncate_text(
            study.abstract or "Abstract not available",
            self.max_abstract_chars
        )

        return COMPACT_USER_PROMPT_TEMPLATE.format(
            research_question=truncate_text(self.research_question, 500),
            population=truncate_text(self.criteria.inclusion.population, 200),
            intervention=truncate_text(self.criteria.inclusion.intervention, 200),
            comparison=truncate_text(self.criteria.inclusion.comparison, 150),
            outcome=truncate_text(self.criteria.inclusion.outcome, 200),
            study_design=truncate_text(self.criteria.inclusion.study_design, 150),
            exclusion_criteria=truncate_text(self._exclusion_str, 300),
            title=title,
            abstract=abstract,
        )

    def _parse_response(self, response_content: str) -> dict:
        """
        Parse the LLM response JSON.

        Args:
            response_content: Raw response content

        Returns:
            Parsed dictionary
        """
        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_content)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # Return safe default if parsing fails
            logger.warning(f"Failed to parse response: {response_content[:200]}")
            return {
                "decision": "included",
                "reason": "Unable to parse LLM response - including for manual review",
                "reason_category": "other",
                "confidence": 0.5
            }

    def _create_fallback_decision(self, study: Study, error_msg: str) -> ScreeningDecision:
        """
        Create a fallback decision when screening fails.

        Args:
            study: Study that failed to screen
            error_msg: Error message

        Returns:
            Safe fallback ScreeningDecision
        """
        logger.warning(f"Creating fallback decision for study {study.id}: {error_msg}")

        return ScreeningDecision(
            study_id=study.id,
            phase=ScreeningPhase.TITLE_ABSTRACT,
            decision="included",  # Include for manual review on failure
            reason=f"Unable to screen automatically: {error_msg[:100]}",
            reason_category=ExclusionCategory.OTHER,
            confidence=0.0,  # Zero confidence indicates manual review needed
        )

    def screen_study(self, study: Study, use_cache: bool = True) -> ScreeningDecision:
        """
        Screen a single study.

        Args:
            study: Study to screen
            use_cache: Whether to use cached results

        Returns:
            ScreeningDecision with result
        """
        # Check cache first
        if use_cache:
            cache_key = get_study_hash(study)
            if cache_key in self._decision_cache:
                logger.debug(f"Cache hit for study {study.id}")
                return self._decision_cache[cache_key]

        # Build prompt
        prompt = self._build_prompt(study)

        messages = [
            {"role": "system", "content": COMPACT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        # Call LLM with safe fallback
        try:
            # Check if client has chat_safe method (OpenAI client does)
            if hasattr(self.llm_client, 'chat_safe'):
                response = self.llm_client.chat_safe(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=200,  # Reduced from 300
                    json_mode=True,
                )
            else:
                response = self.llm_client.chat(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=200,
                    json_mode=True,
                )
        except Exception as e:
            logger.error(f"LLM call failed for study {study.id}: {e}")
            decision = self._create_fallback_decision(study, str(e))

            # Cache and return
            if use_cache:
                self._decision_cache[get_study_hash(study)] = decision
            return decision

        # Parse response
        data = self._parse_response(response.content)

        # Check for API error in response
        if data.get("error") == "unable_to_screen":
            decision = self._create_fallback_decision(
                study,
                data.get("reason", "Unknown error")
            )
        else:
            # Map reason category
            reason_category_str = data.get("reason_category", "other").lower()
            try:
                reason_category = ExclusionCategory(reason_category_str)
            except ValueError:
                reason_category = ExclusionCategory.OTHER

            # Create decision
            decision = ScreeningDecision(
                study_id=study.id,
                phase=ScreeningPhase.TITLE_ABSTRACT,
                decision=data.get("decision", "included"),
                reason=data.get("reason", ""),
                reason_category=reason_category,
                confidence=float(data.get("confidence", 0.8)),
            )

        # Track cost
        if self.cost_tracker and response.total_tokens > 0:
            self.cost_tracker.add_cost(
                operation=OperationType.TITLE_ABSTRACT_SCREENING,
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
                operation="title_abstract_screening",
                prompt=prompt,
                response=response.content,
                decision=decision.decision,
                confidence=decision.confidence,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        # Cache the decision
        if use_cache:
            self._decision_cache[get_study_hash(study)] = decision

        return decision

    def screen_batch(
        self,
        studies: list[Study],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        stop_on_budget: bool = True,
        skip_cached: bool = True,
    ) -> tuple[list[ScreeningDecision], bool]:
        """
        Screen a batch of studies sequentially.

        Args:
            studies: List of studies to screen
            progress_callback: Optional callback(current, total, status) for progress updates
            stop_on_budget: If True, stop when budget exceeded
            skip_cached: If True, skip studies already in cache

        Returns:
            Tuple of (list of decisions, completed flag)
            completed is False if stopped due to budget
        """
        decisions = []
        total = len(studies)
        skipped = 0

        for i, study in enumerate(studies):
            # Check cache first
            cache_key = get_study_hash(study)
            if skip_cached and cache_key in self._decision_cache:
                decisions.append(self._decision_cache[cache_key])
                skipped += 1
                logger.debug(f"Skipped cached study {i+1}/{total}")
                continue

            if progress_callback:
                status = f"Screening: {study.title[:50]}..."
                if skipped > 0:
                    status += f" (skipped {skipped} cached)"
                progress_callback(i, total, status)

            try:
                decision = self.screen_study(study, use_cache=True)
                decisions.append(decision)
            except BudgetExceededError:
                if stop_on_budget:
                    if progress_callback:
                        progress_callback(i, total, "Stopped: Budget limit exceeded")
                    return decisions, False
                raise
            except Exception as e:
                # Log error but continue with fallback decision
                logger.error(f"Error screening study {study.id}: {e}")
                decision = self._create_fallback_decision(study, str(e))
                decisions.append(decision)

        if progress_callback:
            progress_callback(total, total, "Screening complete")

        return decisions, True

    def clear_cache(self) -> int:
        """
        Clear the decision cache.

        Returns:
            Number of entries cleared
        """
        count = len(self._decision_cache)
        self._decision_cache.clear()
        return count

    def get_cached_count(self) -> int:
        """Get number of cached decisions."""
        return len(self._decision_cache)

    def screen_dataframe(
        self,
        df: pd.DataFrame,
        title_col: str = "Title",
        abstract_col: str = "Abstract",
        id_col: Optional[str] = None,
        pmid_col: Optional[str] = None,
        doi_col: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> pd.DataFrame:
        """
        Screen studies from a DataFrame.

        Args:
            df: DataFrame with study data
            title_col: Column name for titles
            abstract_col: Column name for abstracts
            id_col: Optional column for study IDs
            pmid_col: Optional column for PMIDs
            doi_col: Optional column for DOIs
            progress_callback: Optional progress callback

        Returns:
            DataFrame with added decision columns
        """
        # Convert DataFrame to Study objects
        studies = []
        for idx, row in df.iterrows():
            study = Study(
                id=str(row[id_col]) if id_col and id_col in row else str(idx),
                title=str(row[title_col]) if title_col in row else "",
                abstract=str(row[abstract_col]) if abstract_col in row and pd.notna(row[abstract_col]) else None,
                pmid=str(row[pmid_col]) if pmid_col and pmid_col in row and pd.notna(row[pmid_col]) else None,
                doi=str(row[doi_col]) if doi_col and doi_col in row and pd.notna(row[doi_col]) else None,
            )
            studies.append(study)

        # Screen all studies
        decisions, completed = self.screen_batch(studies, progress_callback)

        # Build results DataFrame
        results = df.copy()
        results["screening_decision"] = None
        results["screening_reason"] = None
        results["screening_category"] = None
        results["screening_confidence"] = None

        # Map decisions back to DataFrame
        decision_map = {d.study_id: d for d in decisions}
        for idx, study in enumerate(studies):
            if study.id in decision_map:
                d = decision_map[study.id]
                results.loc[idx, "screening_decision"] = d.decision
                results.loc[idx, "screening_reason"] = d.reason
                results.loc[idx, "screening_category"] = d.reason_category.value
                results.loc[idx, "screening_confidence"] = d.confidence

        return results

    def get_statistics(self, decisions: list[ScreeningDecision]) -> dict:
        """
        Get screening statistics.

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

        # Confidence statistics
        confidences = [d.confidence for d in decisions]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        low_confidence = [d for d in decisions if d.confidence < 0.8]
        failed = [d for d in decisions if d.confidence == 0.0]

        return {
            "total": len(decisions),
            "included": len(included),
            "excluded": len(excluded),
            "inclusion_rate": len(included) / len(decisions) if decisions else 0,
            "exclusion_by_category": category_counts,
            "average_confidence": avg_confidence,
            "low_confidence_count": len(low_confidence),
            "failed_screening_count": len(failed),
        }

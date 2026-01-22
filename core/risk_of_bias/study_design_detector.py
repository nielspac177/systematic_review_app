"""Study design detection for automatic RoB tool selection.

Detects study design from manuscript text to suggest the appropriate
Risk of Bias assessment tool.
"""

import json
import re
from typing import Optional, Tuple
from dataclasses import dataclass

from ..storage.models import Study, RoBToolType
from ..llm.base_client import BaseLLMClient
from ..llm.cost_tracker import CostTracker, OperationType
from .prompts import STUDY_DESIGN_DETECTION_SYSTEM, STUDY_DESIGN_DETECTION_USER


@dataclass
class StudyDesignResult:
    """Result of study design detection."""
    study_design: str
    confidence: float
    reasoning: str
    recommended_tool: RoBToolType
    detection_method: str  # "keyword" or "llm"


class StudyDesignDetector:
    """Detect study design to suggest appropriate RoB tool."""

    # Keyword patterns for high-confidence detection
    RCT_KEYWORDS = [
        r'\brandomized\b', r'\brandomised\b', r'\brandom allocation\b',
        r'\brct\b', r'\brandomly assigned\b', r'\brandom assignment\b',
        r'\bdouble[- ]blind\b', r'\bsingle[- ]blind\b', r'\bplacebo[- ]controlled\b'
    ]

    COHORT_KEYWORDS = [
        r'\bcohort\b', r'\bprospective\b', r'\bretrospective\b',
        r'\bfollow[- ]up\b', r'\blongitudinal\b', r'\bexposed.*unexposed\b'
    ]

    CASE_CONTROL_KEYWORDS = [
        r'\bcase[- ]control\b', r'\bcases and controls\b',
        r'\bmatched controls\b', r'\bodds ratio\b'
    ]

    CROSS_SECTIONAL_KEYWORDS = [
        r'\bcross[- ]sectional\b', r'\bprevalence\b', r'\bsurvey\b',
        r'\bpoint[- ]in[- ]time\b'
    ]

    DIAGNOSTIC_KEYWORDS = [
        r'\bdiagnostic accuracy\b', r'\bsensitivity.*specificity\b',
        r'\breference standard\b', r'\bindex test\b', r'\bauc\b',
        r'\broc curve\b', r'\bgold standard\b'
    ]

    QUALITATIVE_KEYWORDS = [
        r'\bqualitative\b', r'\bphenomenolog\w*\b', r'\bgrounded theory\b',
        r'\bethnograph\w*\b', r'\bthematic analysis\b', r'\binterviews\b',
        r'\bfocus groups?\b'
    ]

    # Non-randomized interventional patterns
    QUASI_EXPERIMENTAL_KEYWORDS = [
        r'\bquasi[- ]experimental\b', r'\bbefore[- ]after\b',
        r'\bpre[- ]post\b', r'\binterrupted time series\b',
        r'\bnon[- ]randomized.*intervention\b'
    ]

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        cost_tracker: Optional[CostTracker] = None,
    ):
        """
        Initialize study design detector.

        Args:
            llm_client: Optional LLM client for complex cases
            cost_tracker: Optional cost tracker
        """
        self.llm_client = llm_client
        self.cost_tracker = cost_tracker

    def _count_keyword_matches(self, text: str, patterns: list[str]) -> int:
        """Count keyword pattern matches in text."""
        text_lower = text.lower()
        count = 0
        for pattern in patterns:
            if re.search(pattern, text_lower):
                count += 1
        return count

    def _keyword_detection(self, study: Study) -> Optional[StudyDesignResult]:
        """
        Attempt to detect study design using keyword matching.

        Returns result if high confidence, None if LLM should be used.
        """
        text = f"{study.title or ''} {study.abstract or ''}"
        if study.pdf_text:
            # Use first 5000 chars of PDF for keyword detection
            text += " " + study.pdf_text[:5000]

        # Count matches for each design
        scores = {
            "RCT": self._count_keyword_matches(text, self.RCT_KEYWORDS),
            "Cohort": self._count_keyword_matches(text, self.COHORT_KEYWORDS),
            "Case-control": self._count_keyword_matches(text, self.CASE_CONTROL_KEYWORDS),
            "Cross-sectional": self._count_keyword_matches(text, self.CROSS_SECTIONAL_KEYWORDS),
            "Diagnostic accuracy": self._count_keyword_matches(text, self.DIAGNOSTIC_KEYWORDS),
            "Qualitative": self._count_keyword_matches(text, self.QUALITATIVE_KEYWORDS),
            "Non-randomized interventional": self._count_keyword_matches(text, self.QUASI_EXPERIMENTAL_KEYWORDS),
        }

        # Find best match
        best_design = max(scores, key=scores.get)
        best_score = scores[best_design]
        second_best = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0

        # Require clear winner with at least 2 matches
        if best_score >= 2 and best_score > second_best * 2:
            tool_map = {
                "RCT": RoBToolType.ROB_2,
                "Cohort": RoBToolType.NEWCASTLE_OTTAWA_COHORT,
                "Case-control": RoBToolType.NEWCASTLE_OTTAWA_CASE_CONTROL,
                "Cross-sectional": RoBToolType.NEWCASTLE_OTTAWA_CROSS_SECTIONAL,
                "Diagnostic accuracy": RoBToolType.QUADAS_2,
                "Qualitative": RoBToolType.JBI_QUALITATIVE,
                "Non-randomized interventional": RoBToolType.ROBINS_I,
            }

            confidence = min(0.95, 0.6 + (best_score * 0.1))

            return StudyDesignResult(
                study_design=best_design,
                confidence=confidence,
                reasoning=f"Detected {best_score} keyword matches for {best_design} study design",
                recommended_tool=tool_map[best_design],
                detection_method="keyword"
            )

        return None  # Need LLM for complex cases

    def _llm_detection(self, study: Study) -> StudyDesignResult:
        """
        Use LLM to detect study design for ambiguous cases.
        """
        if not self.llm_client:
            # Fallback to uncertain cohort if no LLM
            return StudyDesignResult(
                study_design="Unknown",
                confidence=0.3,
                reasoning="Could not determine study design - no LLM available",
                recommended_tool=RoBToolType.NEWCASTLE_OTTAWA_COHORT,
                detection_method="fallback"
            )

        # Prepare fulltext excerpt
        fulltext_excerpt = ""
        if study.pdf_text:
            fulltext_excerpt = f"\nFulltext Excerpt (Methods section):\n{study.pdf_text[:8000]}"

        prompt = STUDY_DESIGN_DETECTION_USER.format(
            title=study.title or "Unknown",
            abstract=study.abstract or "Not available",
            fulltext_excerpt=fulltext_excerpt
        )

        messages = [
            {"role": "system", "content": STUDY_DESIGN_DETECTION_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        response = self.llm_client.chat(
            messages=messages,
            temperature=0.2,
            max_tokens=500,
            json_mode=True
        )

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.RISK_OF_BIAS,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                study_id=study.id,
                model=response.model,
                notes="study_design_detection"
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
                data = {}

        # Map tool string to enum
        tool_map = {
            "rob_2": RoBToolType.ROB_2,
            "robins_i": RoBToolType.ROBINS_I,
            "nos_cohort": RoBToolType.NEWCASTLE_OTTAWA_COHORT,
            "nos_case_control": RoBToolType.NEWCASTLE_OTTAWA_CASE_CONTROL,
            "nos_cross_sectional": RoBToolType.NEWCASTLE_OTTAWA_CROSS_SECTIONAL,
            "quadas_2": RoBToolType.QUADAS_2,
            "jbi_rct": RoBToolType.JBI_RCT,
            "jbi_cohort": RoBToolType.JBI_COHORT,
            "jbi_qualitative": RoBToolType.JBI_QUALITATIVE,
        }

        recommended_tool = tool_map.get(
            data.get("recommended_tool", "nos_cohort"),
            RoBToolType.NEWCASTLE_OTTAWA_COHORT
        )

        return StudyDesignResult(
            study_design=data.get("study_design", "Unknown"),
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning", "LLM-based detection"),
            recommended_tool=recommended_tool,
            detection_method="llm"
        )

    def detect(self, study: Study) -> StudyDesignResult:
        """
        Detect study design and recommend RoB tool.

        Args:
            study: Study to analyze

        Returns:
            StudyDesignResult with design, confidence, and recommended tool
        """
        # Try keyword detection first (fast and cheap)
        keyword_result = self._keyword_detection(study)
        if keyword_result and keyword_result.confidence >= 0.7:
            return keyword_result

        # Use LLM for uncertain cases
        return self._llm_detection(study)

    def suggest_tools_for_project(
        self,
        studies: list[Study],
        progress_callback: Optional[callable] = None
    ) -> dict:
        """
        Analyze all studies in a project to suggest RoB tools.

        Args:
            studies: List of studies to analyze
            progress_callback: Optional progress callback (current, total)

        Returns:
            Dict with tool suggestions and statistics
        """
        results = []
        design_counts = {}
        tool_recommendations = {}

        for i, study in enumerate(studies):
            if progress_callback:
                progress_callback(i + 1, len(studies))

            result = self.detect(study)
            results.append({
                "study_id": study.id,
                "study_title": study.title,
                "result": result
            })

            # Count designs
            design = result.study_design
            design_counts[design] = design_counts.get(design, 0) + 1

            # Count tool recommendations
            tool = result.recommended_tool.value
            tool_recommendations[tool] = tool_recommendations.get(tool, 0) + 1

        # Determine primary tool
        primary_tool = max(tool_recommendations, key=tool_recommendations.get) if tool_recommendations else None

        return {
            "total_studies": len(studies),
            "design_distribution": design_counts,
            "tool_recommendations": tool_recommendations,
            "suggested_primary_tool": primary_tool,
            "detailed_results": results,
            "mixed_designs": len(design_counts) > 1
        }

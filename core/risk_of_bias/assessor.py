"""Risk of Bias Assessor for automated and assisted RoB assessment.

Main class for conducting AI-assisted Risk of Bias assessments following
the DataExtractor pattern.
"""

import json
import hashlib
from typing import Optional, Callable
from datetime import datetime

from ..storage.models import (
    Study, RoBTemplate, RoBToolType, JudgmentLevel,
    StudyRoBAssessment, RoBDomainJudgment, SignalingQuestionResponse,
    RoBAuditEntry
)
from ..llm.base_client import BaseLLMClient
from ..llm.cost_tracker import CostTracker, OperationType, BudgetExceededError
from ..storage.audit_logger import AuditLogger
from .prompts import (
    ROB_ASSESSMENT_SYSTEM, ROB_ASSESSMENT_USER,
    ROB2_DOMAIN_GUIDANCE, ROBINS_I_DOMAIN_GUIDANCE,
    QUADAS2_DOMAIN_GUIDANCE, NOS_ASSESSMENT_GUIDANCE
)


class RoBAssessor:
    """Conduct AI-assisted Risk of Bias assessments."""

    # Maximum characters to send to LLM
    MAX_TEXT_CHARS = 50000

    # Tool-specific guidance mapping
    TOOL_GUIDANCE = {
        RoBToolType.ROB_2: ROB2_DOMAIN_GUIDANCE,
        RoBToolType.ROBINS_I: ROBINS_I_DOMAIN_GUIDANCE,
        RoBToolType.QUADAS_2: QUADAS2_DOMAIN_GUIDANCE,
        RoBToolType.NEWCASTLE_OTTAWA_COHORT: NOS_ASSESSMENT_GUIDANCE,
        RoBToolType.NEWCASTLE_OTTAWA_CASE_CONTROL: NOS_ASSESSMENT_GUIDANCE,
        RoBToolType.NEWCASTLE_OTTAWA_CROSS_SECTIONAL: NOS_ASSESSMENT_GUIDANCE,
    }

    def __init__(
        self,
        llm_client: BaseLLMClient,
        template: RoBTemplate,
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        session_manager=None,
        project_id: Optional[str] = None,
        uncertain_threshold: float = 0.7,
    ):
        """
        Initialize RoB assessor.

        Args:
            llm_client: LLM client for AI assessment
            template: RoB template to use
            cost_tracker: Optional cost tracker
            audit_logger: Optional audit logger
            session_manager: Optional session manager for persistence
            project_id: Optional project ID for saving
            uncertain_threshold: Confidence below this flags as uncertain
        """
        self.llm_client = llm_client
        self.template = template
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.session_manager = session_manager
        self.project_id = project_id
        self.uncertain_threshold = uncertain_threshold
        self._assessment_cache: dict[str, StudyRoBAssessment] = {}

    def _get_study_hash(self, study: Study, comparison_label: Optional[str] = None) -> str:
        """Generate hash for caching."""
        content = f"{study.id}:{study.title}:{self.template.id}:{comparison_label or ''}"
        return hashlib.md5(content.encode()).hexdigest()

    def _truncate_text(self, text: str) -> str:
        """Truncate text to fit within context limits."""
        if len(text) <= self.MAX_TEXT_CHARS:
            return text

        # Keep beginning and end for context
        half = self.MAX_TEXT_CHARS // 2
        return text[:half] + "\n\n[...text truncated...]\n\n" + text[-half:]

    def _build_domains_description(self) -> str:
        """Build formatted description of domains to assess."""
        lines = []
        for domain in sorted(self.template.domains, key=lambda d: d.display_order):
            lines.append(f"\n## {domain.name}")
            lines.append(f"Description: {domain.description}")
            lines.append("\nSignaling Questions:")
            for i, sq in enumerate(domain.signaling_questions, 1):
                lines.append(f"  {i}. {sq.question_text}")
                if sq.guidance:
                    lines.append(f"     Guidance: {sq.guidance}")
                lines.append(f"     Options: {', '.join(sq.response_options)}")
            if domain.judgment_guidance:
                lines.append("\nJudgment Guidance:")
                for level, guidance in domain.judgment_guidance.items():
                    lines.append(f"  - {level}: {guidance}")

        return "\n".join(lines)

    def _get_tool_specific_guidance(self) -> str:
        """Get tool-specific assessment guidance."""
        return self.TOOL_GUIDANCE.get(self.template.tool_type, "")

    def estimate_cost(self, n_studies: int, avg_text_length: int = 20000) -> float:
        """
        Estimate cost for assessing N studies.

        Args:
            n_studies: Number of studies
            avg_text_length: Average text length in characters

        Returns:
            Estimated cost in USD
        """
        # Estimate tokens based on text length and template complexity
        avg_input_tokens = min(avg_text_length // 4, self.MAX_TEXT_CHARS // 4) + 1000
        # Output depends on number of domains
        avg_output_tokens = 200 * len(self.template.domains) + 200

        if self.cost_tracker:
            estimate = self.cost_tracker.estimate_cost(
                llm_client=self.llm_client,
                operation=OperationType.RISK_OF_BIAS,
                n_items=n_studies,
                avg_input_tokens=avg_input_tokens,
                avg_output_tokens=avg_output_tokens,
            )
            return estimate.estimated_cost

        return self.llm_client.estimate_cost(
            avg_input_tokens * n_studies,
            avg_output_tokens * n_studies
        )

    def assess_study(
        self,
        study: Study,
        comparison_label: Optional[str] = None,
        skip_cached: bool = True,
    ) -> StudyRoBAssessment:
        """
        Assess risk of bias for a single study.

        Args:
            study: Study to assess
            comparison_label: Optional label for multi-arm comparisons
            skip_cached: If True, return cached result if available

        Returns:
            StudyRoBAssessment with domain judgments
        """
        # Check cache
        cache_key = self._get_study_hash(study, comparison_label)
        if skip_cached and cache_key in self._assessment_cache:
            return self._assessment_cache[cache_key]

        # Check database
        if skip_cached and self.session_manager and self.project_id:
            existing = self.session_manager.get_rob_assessment(
                self.project_id, study.id, comparison_label
            )
            if existing:
                self._assessment_cache[cache_key] = existing
                return existing

        # Prepare study text
        study_text = self._prepare_study_text(study)

        # Build domains description
        domains_description = self._build_domains_description()

        # Add tool-specific guidance
        tool_guidance = self._get_tool_specific_guidance()
        system_prompt = ROB_ASSESSMENT_SYSTEM + "\n\n" + tool_guidance

        # Build user prompt
        user_prompt = ROB_ASSESSMENT_USER.format(
            tool_name=self.template.name,
            title=study.title or "Unknown",
            authors=study.authors or "Unknown",
            year=study.year or "Unknown",
            study_text=study_text,
            domains_description=domains_description,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Call LLM
        response = self.llm_client.chat(
            messages=messages,
            temperature=0.2,
            max_tokens=4000,
            json_mode=True,
        )

        # Parse response
        assessment = self._parse_assessment_response(
            response.content, study, comparison_label
        )

        # Update cost tracking
        assessment.ai_cost = response.cost
        assessment.ai_model = response.model

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.RISK_OF_BIAS,
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
                operation="risk_of_bias_assessment",
                prompt=user_prompt[:5000] + "..." if len(user_prompt) > 5000 else user_prompt,
                response=response.content,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        # Save RoB-specific audit
        if self.session_manager and self.project_id:
            audit_entry = RoBAuditEntry(
                assessment_id=assessment.id,
                study_id=study.id,
                action="ai_generated",
                new_judgment=assessment.overall_judgment.value,
                notes=f"AI assessment using {self.template.name}",
            )
            self.session_manager.save_rob_audit(self.project_id, audit_entry)

        # Save assessment
        if self.session_manager and self.project_id:
            self.session_manager.save_rob_assessment(self.project_id, assessment)

        # Cache result
        self._assessment_cache[cache_key] = assessment

        return assessment

    def _prepare_study_text(self, study: Study) -> str:
        """Prepare study text for assessment."""
        text_parts = []

        if study.title:
            text_parts.append(f"TITLE: {study.title}")
        if study.abstract:
            text_parts.append(f"\nABSTRACT:\n{study.abstract}")
        if study.pdf_text:
            text_parts.append(f"\nFULL TEXT:\n{study.pdf_text}")

        combined = "\n".join(text_parts)
        return self._truncate_text(combined)

    def _parse_assessment_response(
        self,
        response_content: str,
        study: Study,
        comparison_label: Optional[str]
    ) -> StudyRoBAssessment:
        """Parse LLM response into assessment model."""
        try:
            data = json.loads(response_content)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_content)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = {}

        domain_assessments = data.get("domain_assessments", {})
        domain_judgments = []

        for domain in self.template.domains:
            domain_data = domain_assessments.get(domain.name, {})

            # Parse signaling responses
            signaling_responses = []
            for sr_data in domain_data.get("signaling_responses", []):
                signaling_responses.append(SignalingQuestionResponse(
                    question_id=sr_data.get("question_id", ""),
                    response=sr_data.get("response", "No Information"),
                    supporting_quote=sr_data.get("supporting_quote"),
                    notes=sr_data.get("notes"),
                ))

            # Parse judgment level
            judgment_str = domain_data.get("judgment", "unclear").lower()
            judgment = self._parse_judgment_level(judgment_str)

            # Get confidence and determine if flagged
            confidence = domain_data.get("confidence", 0.5)
            is_flagged = confidence < self.uncertain_threshold

            domain_judgments.append(RoBDomainJudgment(
                domain_id=domain.id,
                domain_name=domain.name,
                signaling_responses=signaling_responses,
                judgment=judgment,
                rationale=domain_data.get("rationale", ""),
                supporting_quotes=domain_data.get("supporting_quotes", []),
                ai_suggested_judgment=judgment,
                ai_confidence=confidence,
                is_ai_generated=True,
                is_human_verified=False,
                is_flagged_uncertain=is_flagged,
            ))

        # Parse overall judgment
        overall_str = data.get("overall_judgment", "unclear").lower()
        overall_judgment = self._parse_judgment_level(overall_str)

        return StudyRoBAssessment(
            study_id=study.id,
            template_id=self.template.id,
            tool_type=self.template.tool_type,
            detected_study_design=None,
            comparison_label=comparison_label,
            domain_judgments=domain_judgments,
            overall_judgment=overall_judgment,
            overall_rationale=data.get("overall_rationale", ""),
            assessment_status="draft",
        )

    def _parse_judgment_level(self, judgment_str: str) -> JudgmentLevel:
        """Parse judgment string to JudgmentLevel enum."""
        judgment_str = judgment_str.lower().replace("_", " ").replace("-", " ")

        mapping = {
            "low": JudgmentLevel.LOW,
            "low risk": JudgmentLevel.LOW,
            "some concerns": JudgmentLevel.SOME_CONCERNS,
            "moderate": JudgmentLevel.MODERATE,
            "serious": JudgmentLevel.SERIOUS,
            "critical": JudgmentLevel.CRITICAL,
            "high": JudgmentLevel.HIGH,
            "high risk": JudgmentLevel.HIGH,
            "unclear": JudgmentLevel.UNCLEAR,
            "not applicable": JudgmentLevel.NOT_APPLICABLE,
            "no information": JudgmentLevel.NO_INFORMATION,
        }

        return mapping.get(judgment_str, JudgmentLevel.UNCLEAR)

    def assess_batch(
        self,
        studies: list[Study],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        stop_on_budget: bool = True,
        skip_cached: bool = True,
    ) -> tuple[list[StudyRoBAssessment], bool]:
        """
        Assess risk of bias for multiple studies.

        Args:
            studies: List of studies to assess
            progress_callback: Optional callback(current, total, message)
            stop_on_budget: If True, stop when budget exceeded
            skip_cached: If True, skip already assessed studies

        Returns:
            Tuple of (list of assessments, completed flag)
        """
        assessments = []
        total = len(studies)

        for i, study in enumerate(studies):
            if progress_callback:
                progress_callback(i, total, f"Assessing: {study.title[:40]}...")

            try:
                assessment = self.assess_study(study, skip_cached=skip_cached)
                assessments.append(assessment)
            except BudgetExceededError:
                if stop_on_budget:
                    if progress_callback:
                        progress_callback(i, total, "Stopped: Budget limit exceeded")
                    return assessments, False
                raise

        if progress_callback:
            progress_callback(total, total, "Assessment complete")

        return assessments, True

    def verify_assessment(
        self,
        assessment: StudyRoBAssessment,
        domain_id: str,
        verified_judgment: JudgmentLevel,
        override_notes: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> StudyRoBAssessment:
        """
        Mark a domain as human-verified with optional override.

        Args:
            assessment: Assessment to update
            domain_id: Domain ID to verify
            verified_judgment: The verified judgment
            override_notes: Notes if overriding AI judgment
            user_id: ID of verifying user

        Returns:
            Updated assessment
        """
        for domain_judgment in assessment.domain_judgments:
            if domain_judgment.domain_id == domain_id:
                # Track if this is an override
                previous_judgment = domain_judgment.judgment

                domain_judgment.is_human_verified = True
                domain_judgment.judgment = verified_judgment
                domain_judgment.is_flagged_uncertain = False

                if verified_judgment != previous_judgment:
                    domain_judgment.human_override_notes = override_notes

                # Log audit entry
                if self.session_manager and self.project_id:
                    action = "human_verify" if verified_judgment == previous_judgment else "human_edit"
                    audit_entry = RoBAuditEntry(
                        assessment_id=assessment.id,
                        study_id=assessment.study_id,
                        action=action,
                        domain_id=domain_id,
                        previous_judgment=previous_judgment.value,
                        new_judgment=verified_judgment.value,
                        user_id=user_id,
                        notes=override_notes,
                    )
                    self.session_manager.save_rob_audit(self.project_id, audit_entry)

                break

        # Recalculate overall judgment
        self._recalculate_overall(assessment)

        # Update assessment status
        all_verified = all(dj.is_human_verified for dj in assessment.domain_judgments)
        if all_verified:
            assessment.assessment_status = "reviewed"

        # Save
        if self.session_manager and self.project_id:
            self.session_manager.save_rob_assessment(self.project_id, assessment)

        return assessment

    def _recalculate_overall(self, assessment: StudyRoBAssessment) -> None:
        """Recalculate overall judgment based on domain judgments."""
        judgments = [dj.judgment for dj in assessment.domain_judgments]

        # Apply tool-specific algorithm
        if self.template.tool_type in [RoBToolType.ROB_2, RoBToolType.JBI_RCT]:
            # Worst-case: High > Some Concerns > Low
            if JudgmentLevel.HIGH in judgments:
                assessment.overall_judgment = JudgmentLevel.HIGH
            elif JudgmentLevel.SOME_CONCERNS in judgments:
                assessment.overall_judgment = JudgmentLevel.SOME_CONCERNS
            else:
                assessment.overall_judgment = JudgmentLevel.LOW

        elif self.template.tool_type == RoBToolType.ROBINS_I:
            # ROBINS-I: Critical > Serious > Moderate > Low
            if JudgmentLevel.CRITICAL in judgments:
                assessment.overall_judgment = JudgmentLevel.CRITICAL
            elif JudgmentLevel.SERIOUS in judgments:
                assessment.overall_judgment = JudgmentLevel.SERIOUS
            elif JudgmentLevel.MODERATE in judgments:
                assessment.overall_judgment = JudgmentLevel.MODERATE
            else:
                assessment.overall_judgment = JudgmentLevel.LOW

        elif self.template.tool_type == RoBToolType.QUADAS_2:
            # QUADAS-2: High > Unclear > Low
            if JudgmentLevel.HIGH in judgments:
                assessment.overall_judgment = JudgmentLevel.HIGH
            elif JudgmentLevel.UNCLEAR in judgments:
                assessment.overall_judgment = JudgmentLevel.UNCLEAR
            else:
                assessment.overall_judgment = JudgmentLevel.LOW

        else:
            # Default: NOS-style based on counting
            # High concerns if multiple high-risk domains
            high_count = sum(1 for j in judgments if j in [JudgmentLevel.HIGH, JudgmentLevel.SERIOUS, JudgmentLevel.CRITICAL])
            if high_count >= 2:
                assessment.overall_judgment = JudgmentLevel.HIGH
            elif high_count == 1 or JudgmentLevel.SOME_CONCERNS in judgments or JudgmentLevel.MODERATE in judgments:
                assessment.overall_judgment = JudgmentLevel.SOME_CONCERNS
            else:
                assessment.overall_judgment = JudgmentLevel.LOW

    def get_statistics(self, assessments: list[StudyRoBAssessment]) -> dict:
        """
        Get assessment statistics.

        Args:
            assessments: List of assessments

        Returns:
            Dictionary with statistics
        """
        if not assessments:
            return {
                "total_studies": 0,
                "by_overall_judgment": {},
                "by_domain": {},
                "flagged_uncertain": 0,
                "verified_count": 0,
            }

        # Overall judgment distribution
        overall_dist = {}
        for a in assessments:
            j = a.overall_judgment.value
            overall_dist[j] = overall_dist.get(j, 0) + 1

        # Domain-level distribution
        domain_dist = {}
        flagged_count = 0
        verified_count = 0

        for a in assessments:
            for dj in a.domain_judgments:
                domain_name = dj.domain_name
                if domain_name not in domain_dist:
                    domain_dist[domain_name] = {}

                j = dj.judgment.value
                domain_dist[domain_name][j] = domain_dist[domain_name].get(j, 0) + 1

                if dj.is_flagged_uncertain:
                    flagged_count += 1
                if dj.is_human_verified:
                    verified_count += 1

        total_domains = sum(len(a.domain_judgments) for a in assessments)

        return {
            "total_studies": len(assessments),
            "by_overall_judgment": overall_dist,
            "by_domain": domain_dist,
            "flagged_uncertain": flagged_count,
            "verified_count": verified_count,
            "total_domain_assessments": total_domains,
            "verification_rate": verified_count / total_domains if total_domains > 0 else 0,
        }

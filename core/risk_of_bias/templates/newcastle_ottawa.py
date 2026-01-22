"""Newcastle-Ottawa Scale (NOS) templates for observational studies.

The Newcastle-Ottawa Scale is a quality assessment tool for non-randomized
studies in meta-analyses. Separate scales exist for cohort and case-control
studies, with an adapted version for cross-sectional studies.

Reference: Wells GA, Shea B, O'Connell D, et al. The Newcastle-Ottawa Scale (NOS)
for assessing the quality of nonrandomised studies in meta-analyses.
"""

from ...storage.models import (
    RoBTemplate, RoBDomainTemplate, SignalingQuestion, RoBToolType
)


def get_nos_cohort_template() -> RoBTemplate:
    """Get the Newcastle-Ottawa Scale template for cohort studies."""

    domains = [
        # Selection domain (max 4 stars)
        RoBDomainTemplate(
            name="Selection",
            short_name="Selection",
            description="Assessment of the selection of the study groups",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Representativeness of the exposed cohort: Is the exposed cohort truly or somewhat representative of the average person in the community?",
                    guidance="Award a star if: truly representative (e.g., all eligible, or random sample) OR somewhat representative.",
                    response_options=["Truly representative (1 star)", "Somewhat representative (1 star)", "Selected group (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Selection of the non-exposed cohort: Was the non-exposed cohort drawn from the same community as the exposed cohort?",
                    guidance="Award a star if the non-exposed cohort came from the same community as the exposed.",
                    response_options=["Same community (1 star)", "Different source (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Ascertainment of exposure: How was exposure ascertained?",
                    guidance="Award a star if exposure was ascertained via secure records or structured interview.",
                    response_options=["Secure record (1 star)", "Structured interview (1 star)", "Written self-report (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Demonstration that outcome of interest was not present at start of study",
                    guidance="Award a star if the study demonstrated outcome was not present at baseline.",
                    response_options=["Yes (1 star)", "No (no star)"]
                ),
            ],
            judgment_guidance={
                "low": "3-4 stars awarded in selection (good selection).",
                "some_concerns": "2 stars awarded in selection (fair selection).",
                "high": "0-1 stars awarded in selection (poor selection)."
            },
            display_order=1
        ),

        # Comparability domain (max 2 stars)
        RoBDomainTemplate(
            name="Comparability",
            short_name="Comparability",
            description="Assessment of the comparability of cohorts on the basis of the design or analysis",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Did the study control for the most important factor?",
                    guidance="Award one star if the study controlled for the most important confounder (e.g., age).",
                    response_options=["Yes (1 star)", "No (no star)"]
                ),
                SignalingQuestion(
                    question_text="Did the study control for any additional important factor?",
                    guidance="Award one star if the study controlled for any other important confounder.",
                    response_options=["Yes (1 star)", "No (no star)"]
                ),
            ],
            judgment_guidance={
                "low": "2 stars awarded (good comparability).",
                "some_concerns": "1 star awarded (fair comparability).",
                "high": "0 stars awarded (poor comparability)."
            },
            display_order=2
        ),

        # Outcome domain (max 3 stars)
        RoBDomainTemplate(
            name="Outcome",
            short_name="Outcome",
            description="Assessment of the outcome",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Assessment of outcome: How was the outcome assessed?",
                    guidance="Award a star if outcome was assessed by independent blind assessment or record linkage.",
                    response_options=["Independent blind assessment (1 star)", "Record linkage (1 star)", "Self-report (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Was follow-up long enough for outcomes to occur?",
                    guidance="Award a star if the follow-up was adequate for outcomes to be captured.",
                    response_options=["Yes (1 star)", "No (no star)"]
                ),
                SignalingQuestion(
                    question_text="Adequacy of follow-up of cohorts: Was the follow-up complete enough?",
                    guidance="Award a star if: complete follow-up, subjects lost unlikely to introduce bias, OR loss <20% with adequate description.",
                    response_options=["Complete follow-up (1 star)", "Minimal lost to follow-up (1 star)", "Follow-up rate <80% (no star)", "No statement (no star)"]
                ),
            ],
            judgment_guidance={
                "low": "2-3 stars awarded in outcome (good outcome assessment).",
                "some_concerns": "1 star awarded in outcome (fair outcome assessment).",
                "high": "0 stars awarded in outcome (poor outcome assessment)."
            },
            display_order=3
        ),
    ]

    return RoBTemplate(
        tool_type=RoBToolType.NEWCASTLE_OTTAWA_COHORT,
        name="Newcastle-Ottawa Scale (Cohort Studies)",
        version="1.0",
        description="The Newcastle-Ottawa Scale for cohort studies assesses quality across three domains: Selection (max 4 stars), Comparability (max 2 stars), and Outcome (max 3 stars). Maximum total score is 9 stars. Studies with 7-9 stars are typically considered high quality.",
        applicable_study_designs=["Cohort study", "Prospective cohort", "Retrospective cohort"],
        domains=domains,
        overall_judgment_algorithm="""
        Overall quality based on total star count:
        - 7-9 stars: Low risk of bias (Good quality)
        - 4-6 stars: Some concerns (Fair quality)
        - 0-3 stars: High risk of bias (Poor quality)
        """,
        is_builtin=True,
        is_customized=False,
    )


def get_nos_case_control_template() -> RoBTemplate:
    """Get the Newcastle-Ottawa Scale template for case-control studies."""

    domains = [
        # Selection domain (max 4 stars)
        RoBDomainTemplate(
            name="Selection",
            short_name="Selection",
            description="Assessment of the selection of cases and controls",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Is the case definition adequate?",
                    guidance="Award a star if cases were independently validated or if validation by record linkage or self-report.",
                    response_options=["Independent validation (1 star)", "Record linkage or self-report (1 star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Representativeness of the cases: Are the cases representative?",
                    guidance="Award a star if cases are consecutive or obviously representative.",
                    response_options=["Consecutive or representative (1 star)", "Potential for selection bias (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Selection of controls: How were controls selected?",
                    guidance="Award a star if controls were community-based.",
                    response_options=["Community controls (1 star)", "Hospital controls (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Definition of controls: Is the definition of controls based on absence of disease?",
                    guidance="Award a star if controls had no history of disease.",
                    response_options=["No history of disease (1 star)", "No description of source (no star)"]
                ),
            ],
            judgment_guidance={
                "low": "3-4 stars awarded in selection (good selection).",
                "some_concerns": "2 stars awarded in selection (fair selection).",
                "high": "0-1 stars awarded in selection (poor selection)."
            },
            display_order=1
        ),

        # Comparability domain (max 2 stars)
        RoBDomainTemplate(
            name="Comparability",
            short_name="Comparability",
            description="Assessment of the comparability of cases and controls on the basis of the design or analysis",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Did the study control for the most important factor?",
                    guidance="Award one star if the study controlled for the most important confounder.",
                    response_options=["Yes (1 star)", "No (no star)"]
                ),
                SignalingQuestion(
                    question_text="Did the study control for any additional important factor?",
                    guidance="Award one star if the study controlled for any other important confounder.",
                    response_options=["Yes (1 star)", "No (no star)"]
                ),
            ],
            judgment_guidance={
                "low": "2 stars awarded (good comparability).",
                "some_concerns": "1 star awarded (fair comparability).",
                "high": "0 stars awarded (poor comparability)."
            },
            display_order=2
        ),

        # Exposure domain (max 3 stars)
        RoBDomainTemplate(
            name="Exposure",
            short_name="Exposure",
            description="Assessment of exposure ascertainment",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Ascertainment of exposure: How was exposure ascertained?",
                    guidance="Award a star if exposure was ascertained via secure record or structured interview blinded to case/control status.",
                    response_options=["Secure record (1 star)", "Structured interview (1 star)", "Interview not blinded (no star)", "Written self-report (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Same method of ascertainment for cases and controls?",
                    guidance="Award a star if the same method was used to ascertain exposure for cases and controls.",
                    response_options=["Yes (1 star)", "No (no star)"]
                ),
                SignalingQuestion(
                    question_text="Non-response rate: Was the non-response rate the same for both groups?",
                    guidance="Award a star if the non-response rate was similar between cases and controls.",
                    response_options=["Same rate (1 star)", "Non-respondents described (no star)", "Rate different with no designation (no star)"]
                ),
            ],
            judgment_guidance={
                "low": "2-3 stars awarded in exposure (good exposure assessment).",
                "some_concerns": "1 star awarded in exposure (fair exposure assessment).",
                "high": "0 stars awarded in exposure (poor exposure assessment)."
            },
            display_order=3
        ),
    ]

    return RoBTemplate(
        tool_type=RoBToolType.NEWCASTLE_OTTAWA_CASE_CONTROL,
        name="Newcastle-Ottawa Scale (Case-Control Studies)",
        version="1.0",
        description="The Newcastle-Ottawa Scale for case-control studies assesses quality across three domains: Selection (max 4 stars), Comparability (max 2 stars), and Exposure (max 3 stars). Maximum total score is 9 stars. Studies with 7-9 stars are typically considered high quality.",
        applicable_study_designs=["Case-control study", "Nested case-control"],
        domains=domains,
        overall_judgment_algorithm="""
        Overall quality based on total star count:
        - 7-9 stars: Low risk of bias (Good quality)
        - 4-6 stars: Some concerns (Fair quality)
        - 0-3 stars: High risk of bias (Poor quality)
        """,
        is_builtin=True,
        is_customized=False,
    )


def get_nos_cross_sectional_template() -> RoBTemplate:
    """Get the adapted Newcastle-Ottawa Scale template for cross-sectional studies."""

    domains = [
        # Selection domain
        RoBDomainTemplate(
            name="Selection",
            short_name="Selection",
            description="Assessment of the selection of participants",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Representativeness of the sample: Is the sample truly representative?",
                    guidance="Award a star if the sample is truly representative or somewhat representative of the target population.",
                    response_options=["Truly representative (1 star)", "Somewhat representative (1 star)", "Selected group (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Sample size: Was the sample size adequate?",
                    guidance="Award a star if the sample size was justified and satisfactory.",
                    response_options=["Justified and satisfactory (1 star)", "Not justified (no star)"]
                ),
                SignalingQuestion(
                    question_text="Non-respondents: Was there a description of non-respondents?",
                    guidance="Award a star if there was a satisfactory response rate or non-respondents were described.",
                    response_options=["Satisfactory response (1 star)", "Non-respondents described (1 star)", "Response rate unsatisfactory (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Ascertainment of the exposure: How was the exposure measured?",
                    guidance="Award a star if the exposure was measured using a validated tool.",
                    response_options=["Validated tool (1 star)", "Non-validated but described (no star)", "No description (no star)"]
                ),
            ],
            judgment_guidance={
                "low": "3-4 stars awarded in selection (good selection).",
                "some_concerns": "2 stars awarded in selection (fair selection).",
                "high": "0-1 stars awarded in selection (poor selection)."
            },
            display_order=1
        ),

        # Comparability domain
        RoBDomainTemplate(
            name="Comparability",
            short_name="Comparability",
            description="Assessment of comparability based on design or analysis",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Did the study control for the most important factor?",
                    guidance="Award one star if the study controlled for the most important confounder.",
                    response_options=["Yes (1 star)", "No (no star)"]
                ),
                SignalingQuestion(
                    question_text="Did the study control for any additional important factor?",
                    guidance="Award one star if the study controlled for any other important confounder.",
                    response_options=["Yes (1 star)", "No (no star)"]
                ),
            ],
            judgment_guidance={
                "low": "2 stars awarded (good comparability).",
                "some_concerns": "1 star awarded (fair comparability).",
                "high": "0 stars awarded (poor comparability)."
            },
            display_order=2
        ),

        # Outcome domain
        RoBDomainTemplate(
            name="Outcome",
            short_name="Outcome",
            description="Assessment of the outcome",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Assessment of outcome: How was the outcome assessed?",
                    guidance="Award a star if the outcome was assessed using a validated or objective tool.",
                    response_options=["Independent blind assessment (1 star)", "Record linkage (1 star)", "Self-report (no star)", "No description (no star)"]
                ),
                SignalingQuestion(
                    question_text="Statistical test: Was the statistical test appropriate?",
                    guidance="Award a star if the statistical test was appropriate for the data and clearly described.",
                    response_options=["Appropriate and described (1 star)", "Not appropriate or not described (no star)"]
                ),
            ],
            judgment_guidance={
                "low": "2 stars awarded in outcome (good outcome assessment).",
                "some_concerns": "1 star awarded in outcome (fair outcome assessment).",
                "high": "0 stars awarded in outcome (poor outcome assessment)."
            },
            display_order=3
        ),
    ]

    return RoBTemplate(
        tool_type=RoBToolType.NEWCASTLE_OTTAWA_CROSS_SECTIONAL,
        name="Newcastle-Ottawa Scale (Cross-Sectional Studies)",
        version="1.0",
        description="An adapted Newcastle-Ottawa Scale for cross-sectional studies assesses quality across three domains: Selection (max 4 stars), Comparability (max 2 stars), and Outcome (max 2 stars). Maximum total score is 8 stars.",
        applicable_study_designs=["Cross-sectional study", "Prevalence study"],
        domains=domains,
        overall_judgment_algorithm="""
        Overall quality based on total star count:
        - 6-8 stars: Low risk of bias (Good quality)
        - 4-5 stars: Some concerns (Fair quality)
        - 0-3 stars: High risk of bias (Poor quality)
        """,
        is_builtin=True,
        is_customized=False,
    )

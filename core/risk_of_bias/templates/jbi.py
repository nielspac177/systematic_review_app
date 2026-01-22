"""JBI Critical Appraisal tools templates.

The Joanna Briggs Institute (JBI) critical appraisal tools are designed for
use in systematic reviews to assess the methodological quality of studies.

Reference: Joanna Briggs Institute. Critical Appraisal Tools.
https://jbi.global/critical-appraisal-tools
"""

from ...storage.models import (
    RoBTemplate, RoBDomainTemplate, SignalingQuestion, RoBToolType
)


def get_jbi_rct_template() -> RoBTemplate:
    """Get the JBI Critical Appraisal Checklist for RCTs."""

    domains = [
        RoBDomainTemplate(
            name="Randomization and Allocation",
            short_name="Randomization",
            description="Assessment of randomization and allocation concealment",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Was true randomization used for assignment of participants to treatment groups?",
                    guidance="Consider computer-generated random numbers, coin toss, random number tables, etc.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Was allocation to treatment groups concealed?",
                    guidance="Consider sealed opaque envelopes, central randomization, or other methods.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "True randomization with adequate allocation concealment.",
                "some_concerns": "Randomization described but allocation concealment unclear.",
                "high": "No true randomization or allocation was not concealed."
            },
            display_order=1
        ),

        RoBDomainTemplate(
            name="Blinding",
            short_name="Blinding",
            description="Assessment of blinding procedures",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were participants blind to treatment assignment?",
                    guidance="Consider whether participants were unaware of which intervention they received.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were those delivering treatment blind to treatment assignment?",
                    guidance="Consider whether clinicians/researchers were unaware of allocation.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were outcome assessors blind to treatment assignment?",
                    guidance="Consider whether those measuring outcomes were unaware of allocation.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Adequate blinding of participants, personnel, and outcome assessors.",
                "some_concerns": "Partial blinding (e.g., only outcome assessors blinded).",
                "high": "No blinding, with potential for bias in subjective outcomes."
            },
            display_order=2
        ),

        RoBDomainTemplate(
            name="Groups and Follow-up",
            short_name="Groups",
            description="Assessment of treatment groups and follow-up",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were treatment groups similar at baseline?",
                    guidance="Consider whether baseline characteristics were comparable.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were groups treated identically other than the intervention of interest?",
                    guidance="Consider co-interventions and treatment consistency.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Was follow-up complete and if not, were differences between groups in terms of their follow-up adequately described and analyzed?",
                    guidance="Consider loss to follow-up and handling of missing data.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were participants analyzed in the groups to which they were randomized?",
                    guidance="Consider intention-to-treat analysis.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Comparable groups, identical treatment, complete follow-up, ITT analysis.",
                "some_concerns": "Minor issues with follow-up or group comparability.",
                "high": "Major imbalances, differential treatment, or substantial loss to follow-up."
            },
            display_order=3
        ),

        RoBDomainTemplate(
            name="Outcome Measurement",
            short_name="Outcomes",
            description="Assessment of outcome measurement and analysis",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were outcomes measured in the same way for treatment groups?",
                    guidance="Consider whether outcome assessment was standardized.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were outcomes measured in a reliable way?",
                    guidance="Consider validity and reliability of outcome measures.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Was appropriate statistical analysis used?",
                    guidance="Consider whether the statistical methods were appropriate for the data.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Was the trial design appropriate, and any deviations from the standard RCT design accounted for in the conduct and analysis of the trial?",
                    guidance="Consider cluster, crossover, or other special designs.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Reliable, standardized outcome measurement with appropriate analysis.",
                "some_concerns": "Minor concerns about measurement or analysis.",
                "high": "Unreliable measurement or inappropriate analysis."
            },
            display_order=4
        ),
    ]

    return RoBTemplate(
        tool_type=RoBToolType.JBI_RCT,
        name="JBI Critical Appraisal Checklist for Randomized Controlled Trials",
        version="2017",
        description="The JBI checklist for RCTs contains 13 items assessing randomization, blinding, group comparability, follow-up, outcome measurement, and statistical analysis. Each item is rated as Yes, No, Unclear, or Not Applicable.",
        applicable_study_designs=["RCT", "Randomized Controlled Trial", "Cluster RCT"],
        domains=domains,
        overall_judgment_algorithm="""
        Studies are typically categorized based on 'Yes' responses:
        - Include: Studies with >70% 'Yes' responses
        - Exclude: Studies with critical flaws in randomization or allocation
        - Seek further info: Studies with 50-70% 'Yes' responses
        """,
        is_builtin=True,
        is_customized=False,
    )


def get_jbi_cohort_template() -> RoBTemplate:
    """Get the JBI Critical Appraisal Checklist for Cohort Studies."""

    domains = [
        RoBDomainTemplate(
            name="Sample and Groups",
            short_name="Sample",
            description="Assessment of sample recruitment and group comparability",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were the two groups similar and recruited from the same population?",
                    guidance="Consider whether exposed and unexposed come from the same source.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were the exposures measured similarly to assign people to both exposed and unexposed groups?",
                    guidance="Consider consistency of exposure ascertainment.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Was the exposure measured in a valid and reliable way?",
                    guidance="Consider validity of exposure measurement.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Similar groups from same population with valid exposure measurement.",
                "some_concerns": "Minor differences in groups or exposure measurement.",
                "high": "Non-comparable groups or invalid exposure measurement."
            },
            display_order=1
        ),

        RoBDomainTemplate(
            name="Confounding",
            short_name="Confounding",
            description="Assessment of confounding factors",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were confounding factors identified?",
                    guidance="Consider whether potential confounders were identified a priori.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were strategies to deal with confounding factors stated?",
                    guidance="Consider matching, stratification, regression, or other methods.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Confounders identified and appropriately controlled.",
                "some_concerns": "Some confounders addressed but not comprehensively.",
                "high": "Important confounders not identified or controlled."
            },
            display_order=2
        ),

        RoBDomainTemplate(
            name="Outcome and Follow-up",
            short_name="Outcome",
            description="Assessment of outcome measurement and follow-up",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were participants free of the outcome at the start of the study (or at the moment of exposure)?",
                    guidance="Consider whether outcome status was assessed at baseline.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were outcomes measured in a valid and reliable way?",
                    guidance="Consider validity of outcome measurement.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Was the follow-up time reported and sufficient to be long enough for outcomes to occur?",
                    guidance="Consider whether follow-up was adequate for the outcome.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Was follow-up complete, and if not, were the reasons for loss to follow-up described and explored?",
                    guidance="Consider completeness of follow-up.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were strategies to address incomplete follow-up utilized?",
                    guidance="Consider handling of missing data.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Adequate outcome measurement and complete follow-up.",
                "some_concerns": "Minor issues with follow-up or outcome measurement.",
                "high": "Invalid outcome measurement or substantial loss to follow-up."
            },
            display_order=3
        ),

        RoBDomainTemplate(
            name="Statistical Analysis",
            short_name="Analysis",
            description="Assessment of statistical analysis",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Was appropriate statistical analysis used?",
                    guidance="Consider whether the statistical methods were appropriate.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Appropriate statistical analysis.",
                "some_concerns": "Minor concerns about analysis.",
                "high": "Inappropriate analysis."
            },
            display_order=4
        ),
    ]

    return RoBTemplate(
        tool_type=RoBToolType.JBI_COHORT,
        name="JBI Critical Appraisal Checklist for Cohort Studies",
        version="2017",
        description="The JBI checklist for cohort studies contains 11 items assessing sample recruitment, exposure measurement, confounding, outcome measurement, follow-up, and statistical analysis. Each item is rated as Yes, No, Unclear, or Not Applicable.",
        applicable_study_designs=["Cohort study", "Prospective cohort", "Retrospective cohort"],
        domains=domains,
        overall_judgment_algorithm="""
        Studies are typically categorized based on 'Yes' responses:
        - Include: Studies with >70% 'Yes' responses
        - Exclude: Studies with critical flaws
        - Seek further info: Studies with 50-70% 'Yes' responses
        """,
        is_builtin=True,
        is_customized=False,
    )


def get_jbi_qualitative_template() -> RoBTemplate:
    """Get the JBI Critical Appraisal Checklist for Qualitative Research."""

    domains = [
        RoBDomainTemplate(
            name="Methodology and Methods",
            short_name="Methods",
            description="Assessment of methodological congruity",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Is there congruity between the stated philosophical perspective and the research methodology?",
                    guidance="Consider whether the methodology aligns with the philosophical approach.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Is there congruity between the research methodology and the research question or objectives?",
                    guidance="Consider whether the methodology is appropriate for the research question.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Is there congruity between the research methodology and the methods used to collect data?",
                    guidance="Consider whether data collection methods fit the methodology.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Is there congruity between the research methodology and the representation and analysis of data?",
                    guidance="Consider whether analysis approach fits the methodology.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Is there congruity between the research methodology and the interpretation of results?",
                    guidance="Consider whether interpretation aligns with the methodology.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Strong methodological congruity throughout.",
                "some_concerns": "Minor inconsistencies in methodological approach.",
                "high": "Significant methodological incongruity."
            },
            display_order=1
        ),

        RoBDomainTemplate(
            name="Researcher and Participants",
            short_name="Researcher",
            description="Assessment of researcher positioning and participant representation",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Is there a statement locating the researcher culturally or theoretically?",
                    guidance="Consider reflexivity and researcher positioning.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Is the influence of the researcher on the research, and vice versa, addressed?",
                    guidance="Consider how researcher-participant relationships were managed.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Are participants, and their voices, adequately represented?",
                    guidance="Consider whether participant perspectives are clearly presented.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Clear researcher positioning and adequate participant representation.",
                "some_concerns": "Limited reflexivity or participant voice.",
                "high": "No reflexivity or participant voices not represented."
            },
            display_order=2
        ),

        RoBDomainTemplate(
            name="Ethics and Conclusions",
            short_name="Ethics",
            description="Assessment of ethical considerations and conclusions",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Is the research ethical according to current criteria or, for recent studies, is there evidence of ethical approval by an appropriate body?",
                    guidance="Consider ethical approval and conduct.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Do the conclusions drawn in the research report flow from the analysis, or interpretation, of the data?",
                    guidance="Consider whether conclusions are supported by the data.",
                    response_options=["Yes", "No", "Unclear", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Ethical approval evident and conclusions flow from data.",
                "some_concerns": "Minor concerns about ethics or conclusions.",
                "high": "No ethical approval or conclusions not supported."
            },
            display_order=3
        ),
    ]

    return RoBTemplate(
        tool_type=RoBToolType.JBI_QUALITATIVE,
        name="JBI Critical Appraisal Checklist for Qualitative Research",
        version="2017",
        description="The JBI checklist for qualitative research contains 10 items assessing methodological congruity, researcher positioning, participant representation, ethics, and conclusions. Each item is rated as Yes, No, Unclear, or Not Applicable.",
        applicable_study_designs=["Qualitative study", "Phenomenology", "Grounded theory", "Ethnography", "Qualitative description"],
        domains=domains,
        overall_judgment_algorithm="""
        Studies are typically categorized based on 'Yes' responses:
        - Include: Studies with >70% 'Yes' responses
        - Exclude: Studies with critical methodological flaws
        - Seek further info: Studies with 50-70% 'Yes' responses
        """,
        is_builtin=True,
        is_customized=False,
    )

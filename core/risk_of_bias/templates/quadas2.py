"""QUADAS-2 template for diagnostic accuracy studies.

QUADAS-2 is a tool for evaluating the quality of diagnostic accuracy studies,
revised from the original QUADAS tool.

Reference: Whiting PF, Rutjes AW, Westwood ME, et al. QUADAS-2: a revised tool
for the quality assessment of diagnostic accuracy studies. Ann Intern Med
2011;155(8):529-36.
"""

from ...storage.models import (
    RoBTemplate, RoBDomainTemplate, SignalingQuestion, RoBToolType
)


def get_quadas2_template() -> RoBTemplate:
    """Get the QUADAS-2 template for diagnostic accuracy studies."""

    domains = [
        # Domain 1: Patient Selection
        RoBDomainTemplate(
            name="Patient Selection",
            short_name="Patient Selection",
            description="Assessment of risk of bias and applicability concerns regarding patient selection",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Was a consecutive or random sample of patients enrolled?",
                    guidance="Consider whether the sampling method was clearly described and appropriate.",
                    response_options=["Yes", "No", "Unclear"]
                ),
                SignalingQuestion(
                    question_text="Was a case-control design avoided?",
                    guidance="Case-control designs can lead to spectrum bias and overestimation of accuracy.",
                    response_options=["Yes", "No", "Unclear"]
                ),
                SignalingQuestion(
                    question_text="Did the study avoid inappropriate exclusions?",
                    guidance="Consider whether participants who might be difficult to diagnose were inappropriately excluded.",
                    response_options=["Yes", "No", "Unclear"]
                ),
                SignalingQuestion(
                    question_text="APPLICABILITY: Is there concern that the included patients do not match the review question?",
                    guidance="Consider whether the included patients match the target population specified in the review question.",
                    response_options=["Low concern", "High concern", "Unclear"]
                ),
            ],
            judgment_guidance={
                "low": "Consecutive/random sample, case-control avoided, no inappropriate exclusions, and low applicability concern.",
                "high": "Non-consecutive/non-random sample, case-control design, or inappropriate exclusions that may introduce bias.",
                "unclear": "Insufficient information to determine risk of bias."
            },
            display_order=1
        ),

        # Domain 2: Index Test
        RoBDomainTemplate(
            name="Index Test",
            short_name="Index Test",
            description="Assessment of risk of bias and applicability concerns regarding the index test",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were the index test results interpreted without knowledge of the results of the reference standard?",
                    guidance="Consider whether blinding of index test interpretation was maintained.",
                    response_options=["Yes", "No", "Unclear"]
                ),
                SignalingQuestion(
                    question_text="If a threshold was used, was it pre-specified?",
                    guidance="Data-driven threshold selection can lead to overestimation of accuracy.",
                    response_options=["Yes", "No", "Unclear"]
                ),
                SignalingQuestion(
                    question_text="APPLICABILITY: Is there concern that the index test, its conduct, or interpretation differ from the review question?",
                    guidance="Consider whether the index test matches the specification in the review question.",
                    response_options=["Low concern", "High concern", "Unclear"]
                ),
            ],
            judgment_guidance={
                "low": "Index test interpreted blind to reference standard results, threshold pre-specified, low applicability concern.",
                "high": "Index test interpretation influenced by knowledge of reference standard, or threshold selected to maximize accuracy.",
                "unclear": "Insufficient information to determine risk of bias."
            },
            display_order=2
        ),

        # Domain 3: Reference Standard
        RoBDomainTemplate(
            name="Reference Standard",
            short_name="Reference Standard",
            description="Assessment of risk of bias and applicability concerns regarding the reference standard",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Is the reference standard likely to correctly classify the target condition?",
                    guidance="Consider whether the reference standard is an adequate gold standard.",
                    response_options=["Yes", "No", "Unclear"]
                ),
                SignalingQuestion(
                    question_text="Were the reference standard results interpreted without knowledge of the results of the index test?",
                    guidance="Consider whether blinding of reference standard interpretation was maintained.",
                    response_options=["Yes", "No", "Unclear"]
                ),
                SignalingQuestion(
                    question_text="APPLICABILITY: Is there concern that the target condition as defined by the reference standard does not match the review question?",
                    guidance="Consider whether the target condition definition matches the review question.",
                    response_options=["Low concern", "High concern", "Unclear"]
                ),
            ],
            judgment_guidance={
                "low": "Reference standard likely to correctly classify condition, interpreted blind to index test, low applicability concern.",
                "high": "Reference standard may not correctly classify condition, or interpretation influenced by index test results.",
                "unclear": "Insufficient information to determine risk of bias."
            },
            display_order=3
        ),

        # Domain 4: Flow and Timing
        RoBDomainTemplate(
            name="Flow and Timing",
            short_name="Flow and Timing",
            description="Assessment of risk of bias regarding flow and timing",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Was there an appropriate interval between index test and reference standard?",
                    guidance="Consider whether the time between tests was short enough that the condition would not have changed.",
                    response_options=["Yes", "No", "Unclear"]
                ),
                SignalingQuestion(
                    question_text="Did all patients receive the same reference standard?",
                    guidance="Consider whether differential verification occurred.",
                    response_options=["Yes", "No", "Unclear"]
                ),
                SignalingQuestion(
                    question_text="Were all patients included in the analysis?",
                    guidance="Consider whether all participants were accounted for in the results.",
                    response_options=["Yes", "No", "Unclear"]
                ),
            ],
            judgment_guidance={
                "low": "Appropriate interval, all patients received same reference standard, all patients included in analysis.",
                "high": "Inappropriate interval, differential verification, or important exclusions from analysis.",
                "unclear": "Insufficient information to determine risk of bias."
            },
            display_order=4
        ),
    ]

    return RoBTemplate(
        tool_type=RoBToolType.QUADAS_2,
        name="QUADAS-2 (Quality Assessment of Diagnostic Accuracy Studies)",
        version="2.0",
        description="QUADAS-2 is a quality assessment tool for diagnostic accuracy studies. It assesses risk of bias and applicability concerns across four domains: Patient Selection, Index Test, Reference Standard, and Flow and Timing. Each domain is assessed as Low Risk, High Risk, or Unclear.",
        applicable_study_designs=["Diagnostic accuracy study", "Diagnostic test study", "Validation study"],
        domains=domains,
        overall_judgment_algorithm="""
        Overall risk of bias:
        - If ANY domain is 'High Risk': Overall = 'High Risk of Bias'
        - If NO domain is 'High Risk' but ANY domain is 'Unclear': Overall = 'Unclear Risk of Bias'
        - If ALL domains are 'Low Risk': Overall = 'Low Risk of Bias'

        Applicability concern (separate assessment):
        - If ANY domain has 'High concern': Overall = 'High Applicability Concern'
        - Otherwise: Overall = 'Low Applicability Concern'
        """,
        is_builtin=True,
        is_customized=False,
    )

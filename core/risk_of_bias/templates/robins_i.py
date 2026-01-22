"""ROBINS-I template for non-randomized studies of interventions.

Based on the Risk Of Bias In Non-randomized Studies of Interventions (ROBINS-I)
assessment tool.

Reference: Sterne JA, Hernan MA, Reeves BC, et al. ROBINS-I: a tool for assessing
risk of bias in non-randomised studies of interventions. BMJ 2016;355:i4919.
"""

from ...storage.models import (
    RoBTemplate, RoBDomainTemplate, SignalingQuestion, RoBToolType
)


def get_robins_i_template() -> RoBTemplate:
    """Get the ROBINS-I template for non-randomized studies."""

    domains = [
        # Domain 1: Confounding
        RoBDomainTemplate(
            name="Bias due to confounding",
            short_name="Confounding",
            description="Assessment of risk of bias due to confounding",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Is there potential for confounding of the effect of intervention in this study?",
                    guidance="Consider whether there are prognostic factors that also predict intervention.",
                    response_options=["No", "Yes"]
                ),
                SignalingQuestion(
                    question_text="Was the analysis based on splitting participants' follow up time according to intervention received?",
                    guidance="Immortal time bias can occur if follow-up time is split.",
                    response_options=["No", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Were intervention discontinuations or switches likely to be related to factors that are prognostic for the outcome?",
                    guidance="Consider whether stopping or switching treatment is related to prognosis.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Did the authors use an appropriate analysis method that controlled for all the important confounding domains?",
                    guidance="Consider multivariable regression, propensity score methods, or other appropriate approaches.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY to 1.4: Were confounding domains that were controlled for measured validly and reliably?",
                    guidance="Consider measurement quality of confounders.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Did the authors control for any post-intervention variables that could have been affected by the intervention?",
                    guidance="Controlling for mediators or colliders can introduce bias.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Did the authors use an appropriate analysis method that adjusted for all the important confounding domains AND for time-varying confounding?",
                    guidance="Consider marginal structural models, g-estimation, or similar methods for time-varying confounding.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "No confounding expected, or confounding was appropriately controlled.",
                "moderate": "Confounding is present but was reasonably controlled, OR there is some residual confounding.",
                "serious": "Important confounders were not controlled, substantially biasing the result.",
                "critical": "Critical confounding makes the comparison essentially meaningless."
            },
            display_order=1
        ),

        # Domain 2: Selection of participants
        RoBDomainTemplate(
            name="Bias in selection of participants into the study",
            short_name="Selection",
            description="Assessment of risk of bias in selection of participants",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Was selection of participants into the study (or into the analysis) based on participant characteristics observed after the start of intervention?",
                    guidance="Selection bias can occur if post-intervention characteristics affect inclusion.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY to 2.1: Were the post-intervention variables that influenced selection likely to be associated with intervention?",
                    guidance="Consider whether the selection factors are related to intervention assignment.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY to 2.2: Were the post-intervention variables that influenced selection likely to be influenced by the outcome or a cause of the outcome?",
                    guidance="Conditioning on a collider or outcome can introduce bias.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Do start of follow-up and start of intervention coincide for most participants?",
                    guidance="Immortal time bias occurs when these do not coincide.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY to 2.4: Were adjustment techniques used that are likely to correct for the presence of selection biases?",
                    guidance="Consider appropriate statistical methods to address selection bias.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Selection into the study was not based on post-intervention factors, OR start of follow-up and intervention coincide.",
                "moderate": "Some selection based on post-intervention factors, but unlikely to substantially affect results.",
                "serious": "Important selection bias that substantially affects the result.",
                "critical": "Critical selection bias makes the comparison essentially meaningless."
            },
            display_order=2
        ),

        # Domain 3: Classification of interventions
        RoBDomainTemplate(
            name="Bias in classification of interventions",
            short_name="Classification",
            description="Assessment of risk of bias in classification of interventions",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were intervention groups clearly defined?",
                    guidance="Consider whether intervention status is clearly and consistently defined.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Was the information used to define intervention groups recorded at the start of the intervention?",
                    guidance="Consider timing of intervention ascertainment.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Could classification of intervention status have been affected by knowledge of the outcome or risk of the outcome?",
                    guidance="Consider whether intervention classification is independent of outcome.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
            ],
            judgment_guidance={
                "low": "Intervention status was well defined and reliably measured.",
                "moderate": "Some concerns about intervention definition or measurement.",
                "serious": "Important classification problems that substantially affect the result.",
                "critical": "Intervention classification is essentially meaningless."
            },
            display_order=3
        ),

        # Domain 4: Deviations from intended interventions
        RoBDomainTemplate(
            name="Bias due to deviations from intended interventions",
            short_name="Deviations",
            description="Assessment of risk of bias due to deviations from intended interventions",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were there deviations from the intended intervention beyond what would be expected in usual practice?",
                    guidance="Consider protocol deviations, co-interventions, and treatment switching.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY to 4.1: Were these deviations from intended intervention unbalanced between groups and likely to have affected the outcome?",
                    guidance="Consider whether deviations were differential and impactful.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Were important co-interventions balanced across intervention groups?",
                    guidance="Consider whether other treatments were balanced.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Was the intervention implemented successfully for most participants?",
                    guidance="Consider adherence and implementation quality.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Did study participants adhere to the assigned intervention regimen?",
                    guidance="Consider overall adherence to the intervention.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If N/PN to 4.5: Was an appropriate analysis used to estimate the effect of starting and adhering to the intervention?",
                    guidance="Consider per-protocol analysis with appropriate methods.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "No important deviations, or deviations were balanced and minimal.",
                "moderate": "Some deviations occurred but were reasonably balanced.",
                "serious": "Important unbalanced deviations that substantially affect the result.",
                "critical": "Deviations are so extensive that the comparison is essentially meaningless."
            },
            display_order=4
        ),

        # Domain 5: Missing data
        RoBDomainTemplate(
            name="Bias due to missing data",
            short_name="Missing data",
            description="Assessment of risk of bias due to missing data",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were outcome data available for all, or nearly all, participants?",
                    guidance="Consider the proportion of participants with outcome data.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Were participants excluded due to missing data on intervention status?",
                    guidance="Consider exclusions due to missing intervention data.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Were participants excluded due to missing data on other variables needed for the analysis?",
                    guidance="Consider exclusions due to missing confounder or other data.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If N/PN to 5.1, 5.2, or 5.3: Are the proportion of participants and reasons for missing data similar across interventions?",
                    guidance="Consider whether missingness is differential.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="If N/PN to 5.1, 5.2, or 5.3: Is there evidence that results were robust to the presence of missing data?",
                    guidance="Consider sensitivity analyses for missing data.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Data were available for (nearly) all participants.",
                "moderate": "Some missing data, but unlikely to depend on true outcome values.",
                "serious": "Substantial missing data likely related to outcomes.",
                "critical": "Missing data make the comparison essentially meaningless."
            },
            display_order=5
        ),

        # Domain 6: Measurement of outcomes
        RoBDomainTemplate(
            name="Bias in measurement of outcomes",
            short_name="Measurement",
            description="Assessment of risk of bias in measurement of outcomes",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Could the outcome measure have been influenced by knowledge of the intervention received?",
                    guidance="Consider blinding and objectivity of outcome measurement.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Were outcome assessors aware of the intervention received by study participants?",
                    guidance="Consider whether outcome assessors were blinded.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Were the methods of outcome assessment comparable across intervention groups?",
                    guidance="Consider whether the same methods were used for all groups.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Were any systematic errors in measurement of the outcome related to intervention received?",
                    guidance="Consider differential measurement error.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
            ],
            judgment_guidance={
                "low": "Outcome measurement was objective, OR assessors were blinded, OR measurement was identical across groups.",
                "moderate": "Some concerns about outcome measurement, but unlikely to substantially affect results.",
                "serious": "Important measurement bias that substantially affects the result.",
                "critical": "Measurement bias makes the comparison essentially meaningless."
            },
            display_order=6
        ),

        # Domain 7: Selection of reported result
        RoBDomainTemplate(
            name="Bias in selection of the reported result",
            short_name="Reporting",
            description="Assessment of risk of bias in selection of the reported result",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Is the reported effect estimate unlikely to be selected, on the basis of the results, from multiple outcome measurements within the outcome domain?",
                    guidance="Consider whether multiple measurements were available and selection might have occurred.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Is the reported effect estimate unlikely to be selected, on the basis of the results, from multiple analyses of the intervention-outcome relationship?",
                    guidance="Consider whether multiple analysis approaches were possible.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Is the reported effect estimate unlikely to be selected, on the basis of the results, from different subgroups?",
                    guidance="Consider whether subgroup analyses were pre-specified.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
            ],
            judgment_guidance={
                "low": "No indication of selective reporting.",
                "moderate": "Some concerns about selective reporting.",
                "serious": "Clear evidence of selective reporting that substantially affects the result.",
                "critical": "Selective reporting makes the result essentially meaningless."
            },
            display_order=7
        ),
    ]

    return RoBTemplate(
        tool_type=RoBToolType.ROBINS_I,
        name="ROBINS-I (Risk Of Bias In Non-randomized Studies of Interventions)",
        version="1.0",
        description="ROBINS-I assesses risk of bias in non-randomized studies of interventions. It covers seven domains: confounding, selection, classification of interventions, deviations from intended interventions, missing data, measurement of outcomes, and selection of reported result. Judgments range from Low to Critical risk of bias.",
        applicable_study_designs=["Cohort study", "Case-control study", "Interrupted time series", "Before-after study", "Non-randomized controlled trial"],
        domains=domains,
        overall_judgment_algorithm="""
        Overall judgment follows the worst domain judgment:
        - If ANY domain is 'Critical': Overall = 'Critical'
        - If ANY domain is 'Serious' (and none Critical): Overall = 'Serious'
        - If ANY domain is 'Moderate' (and none Serious/Critical): Overall = 'Moderate'
        - If ALL domains are 'Low': Overall = 'Low'
        """,
        is_builtin=True,
        is_customized=False,
    )

"""Cochrane Risk of Bias 2 (RoB 2) template for RCTs.

Based on the Cochrane RoB 2 tool (revised 2019) for assessing risk of bias
in randomized controlled trials.

Reference: Sterne JAC, Savovic J, Page MJ, et al. RoB 2: a revised tool for
assessing risk of bias in randomised trials. BMJ 2019;366:l4898.
"""

from ...storage.models import (
    RoBTemplate, RoBDomainTemplate, SignalingQuestion, RoBToolType
)


def get_rob2_template() -> RoBTemplate:
    """Get the standard Cochrane RoB 2 template for RCTs."""

    domains = [
        # Domain 1: Randomization process
        RoBDomainTemplate(
            name="Bias arising from the randomization process",
            short_name="Randomization",
            description="Assessment of risk of bias arising from the randomization process",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Was the allocation sequence random?",
                    guidance="Consider computer-generated sequences, random number tables, coin flipping, etc. Simple alternation, hospital/clinic ID numbers, or dates are not adequate.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Was the allocation sequence concealed until participants were enrolled and assigned to interventions?",
                    guidance="Consider central randomization, sequentially numbered sealed opaque envelopes, sequentially numbered drug containers of identical appearance.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Did baseline differences between intervention groups suggest a problem with the randomization process?",
                    guidance="Examine baseline characteristics for important imbalances that would be unexpected if randomization was adequate.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
            ],
            judgment_guidance={
                "low": "Allocation was adequately randomized and concealed, with no baseline imbalances suggesting problems.",
                "some_concerns": "Information is missing about randomization or concealment, OR there are baseline imbalances that may be due to chance.",
                "high": "The allocation sequence was not random, OR allocation was not concealed, OR baseline imbalances suggest a problem with randomization."
            },
            display_order=1
        ),

        # Domain 2: Deviations from intended interventions
        RoBDomainTemplate(
            name="Bias due to deviations from intended interventions",
            short_name="Deviations",
            description="Assessment of risk of bias due to deviations from the intended interventions (effect of assignment)",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were participants aware of their assigned intervention during the trial?",
                    guidance="Consider whether blinding of participants was attempted and successful.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Were carers and people delivering the interventions aware of participants' assigned intervention during the trial?",
                    guidance="Consider whether blinding of carers/personnel was attempted and successful.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY/NI to 2.1 or 2.2: Were there deviations from the intended intervention that arose because of the trial context?",
                    guidance="Consider deviations that occurred specifically because of the trial (not deviations that would occur in usual practice).",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY to 2.3: Were these deviations likely to have affected the outcome?",
                    guidance="Consider whether the deviations were substantial enough to potentially affect outcome results.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY to 2.4: Were these deviations from intended intervention balanced between groups?",
                    guidance="Consider whether deviations occurred equally across groups.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="Was an appropriate analysis used to estimate the effect of assignment to intervention?",
                    guidance="For effect of assignment, intention-to-treat analysis is usually appropriate.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
            ],
            judgment_guidance={
                "low": "Participants, carers and outcome assessors were blinded to intervention groups, OR deviations were minimal and balanced.",
                "some_concerns": "Some awareness of intervention assignment, but deviations were minimal or appeared balanced.",
                "high": "Substantial deviations from intended intervention that were unbalanced between groups and likely affected outcomes."
            },
            display_order=2
        ),

        # Domain 3: Missing outcome data
        RoBDomainTemplate(
            name="Bias due to missing outcome data",
            short_name="Missing data",
            description="Assessment of risk of bias due to missing outcome data",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were data for this outcome available for all, or nearly all, participants randomized?",
                    guidance="Consider the proportion of participants with missing data. 'Nearly all' typically means >95%.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If N/PN/NI to 3.1: Is there evidence that the result was not biased by missing outcome data?",
                    guidance="Consider sensitivity analyses, pattern of missingness, reasons for missing data.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="If N/PN to 3.2: Could missingness in the outcome depend on its true value?",
                    guidance="Consider whether participants with poor/good outcomes might have been more likely to be lost to follow-up.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY/NI to 3.3: Is it likely that missingness in the outcome depended on its true value?",
                    guidance="Consider whether there is a plausible mechanism linking missingness to the outcome.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Outcome data were available for (nearly) all participants, OR missing data were handled appropriately.",
                "some_concerns": "There is moderate missingness but no clear indication of bias.",
                "high": "Substantial missing data that likely depends on the true outcome value."
            },
            display_order=3
        ),

        # Domain 4: Measurement of the outcome
        RoBDomainTemplate(
            name="Bias in measurement of the outcome",
            short_name="Outcome measurement",
            description="Assessment of risk of bias in measurement of the outcome",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Was the method of measuring the outcome inappropriate?",
                    guidance="Consider whether the outcome measure is valid and reliable.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Could measurement or ascertainment of the outcome have differed between intervention groups?",
                    guidance="Consider whether the same methods were used consistently across groups.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If N/PN/NI to 4.1 and 4.2: Were outcome assessors aware of the intervention received by study participants?",
                    guidance="Consider whether outcome assessors were blinded to intervention assignment.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY/NI to 4.3: Could assessment of the outcome have been influenced by knowledge of intervention received?",
                    guidance="Consider whether the outcome is objective or subjective, and whether assessor knowledge could affect measurement.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "Not Applicable"]
                ),
                SignalingQuestion(
                    question_text="If Y/PY/NI to 4.4: Is it likely that assessment of the outcome was influenced by knowledge of intervention received?",
                    guidance="Consider whether there is evidence that assessor knowledge actually affected measurement.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "Not Applicable"]
                ),
            ],
            judgment_guidance={
                "low": "Outcome measurement method was appropriate, assessors were blinded, OR outcome was objective.",
                "some_concerns": "Assessors may have been aware of intervention, but outcome was relatively objective.",
                "high": "Outcome assessment was likely influenced by knowledge of intervention received."
            },
            display_order=4
        ),

        # Domain 5: Selection of the reported result
        RoBDomainTemplate(
            name="Bias in selection of the reported result",
            short_name="Selective reporting",
            description="Assessment of risk of bias in selection of the reported result",
            signaling_questions=[
                SignalingQuestion(
                    question_text="Were the data that produced this result analysed in accordance with a pre-specified analysis plan that was finalized before unblinded outcome data were available for analysis?",
                    guidance="Consider pre-registration of analysis plan, statistical analysis plan, or protocol.",
                    response_options=["Yes", "Probably Yes", "Probably No", "No", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Is the numerical result being assessed likely to have been selected, on the basis of the results, from multiple eligible outcome measurements within the outcome domain?",
                    guidance="Consider whether multiple measurements of the same outcome were reported and whether selection might have occurred.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
                SignalingQuestion(
                    question_text="Is the numerical result being assessed likely to have been selected, on the basis of the results, from multiple eligible analyses of the data?",
                    guidance="Consider whether multiple analysis approaches were used and whether selection might have occurred.",
                    response_options=["No", "Probably No", "Probably Yes", "Yes", "No Information"]
                ),
            ],
            judgment_guidance={
                "low": "Analysis was clearly pre-specified and reported completely, with no indication of selective reporting.",
                "some_concerns": "There is no clear pre-specification, but no strong indications of selective reporting.",
                "high": "There is strong suspicion that results were selected based on their significance or direction."
            },
            display_order=5
        ),
    ]

    return RoBTemplate(
        tool_type=RoBToolType.ROB_2,
        name="Cochrane Risk of Bias 2 (RoB 2)",
        version="2.0",
        description="The revised Cochrane risk-of-bias tool for randomized trials (RoB 2) assesses the risk of bias in the results of a randomized trial. It covers five domains: randomization process, deviations from intended interventions, missing outcome data, measurement of the outcome, and selection of the reported result.",
        applicable_study_designs=["RCT", "Randomized Controlled Trial", "Cluster RCT", "Crossover RCT"],
        domains=domains,
        overall_judgment_algorithm="""
        Overall judgment is determined by the worst judgment across all domains:
        - If ANY domain is 'High Risk': Overall = 'High Risk'
        - If NO domain is 'High Risk' but ANY domain is 'Some Concerns': Overall = 'Some Concerns'
        - If ALL domains are 'Low Risk': Overall = 'Low Risk'
        """,
        is_builtin=True,
        is_customized=False,
    )

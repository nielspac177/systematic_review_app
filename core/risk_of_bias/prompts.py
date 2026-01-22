"""Prompt templates for Risk of Bias assessments.

These prompts are used by the RoBAssessor class to interact with LLM
for automated risk of bias assessment.
"""

# =============================================================================
# STUDY DESIGN DETECTION PROMPTS
# =============================================================================

STUDY_DESIGN_DETECTION_SYSTEM = """You are an expert systematic review methodologist.
Your task is to identify the study design from research manuscripts to determine
the appropriate Risk of Bias assessment tool to use.

You should classify studies into one of these categories:
- RCT (Randomized Controlled Trial) - includes parallel, cluster, and crossover RCTs
- Non-randomized interventional study - includes quasi-experimental, before-after studies
- Cohort study - includes prospective and retrospective cohorts
- Case-control study - includes nested case-control
- Cross-sectional study - includes prevalence studies
- Diagnostic accuracy study - includes validation studies
- Qualitative study - includes phenomenology, grounded theory, ethnography

Be careful to distinguish between:
- RCTs (random allocation mentioned) vs quasi-experimental (no random allocation)
- Cohort studies (follow-up over time) vs cross-sectional (single time point)
- Case-control (comparing cases vs controls) vs cohort (comparing exposed vs unexposed)"""

STUDY_DESIGN_DETECTION_USER = """Analyze this study to determine its study design.

Study Information:
Title: {title}
Abstract: {abstract}
{fulltext_excerpt}

Based on the available information, identify:
1. The study design
2. Your confidence in this assessment (0.0-1.0)
3. The recommended Risk of Bias tool

Respond in JSON format:
{{
    "study_design": "RCT" | "Non-randomized interventional" | "Cohort" | "Case-control" | "Cross-sectional" | "Diagnostic accuracy" | "Qualitative" | "Other",
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief explanation of key features that led to this classification",
    "recommended_tool": "rob_2" | "robins_i" | "nos_cohort" | "nos_case_control" | "nos_cross_sectional" | "quadas_2" | "jbi_rct" | "jbi_cohort" | "jbi_qualitative"
}}"""

# =============================================================================
# GENERAL ROB ASSESSMENT PROMPTS
# =============================================================================

ROB_ASSESSMENT_SYSTEM = """You are an expert systematic review methodologist conducting
Risk of Bias assessments. Your task is to carefully evaluate studies against
specific RoB domains and signaling questions, providing evidence-based judgments.

Key principles:
1. Base all judgments on explicit information in the manuscript
2. Provide verbatim quotes as evidence for each judgment
3. When information is missing, indicate "No Information" rather than assuming
4. Consider the specific guidance for each signaling question
5. Be consistent in applying the assessment criteria

For each domain, you must:
- Answer each signaling question based on the text
- Provide supporting quotes from the manuscript
- Make a domain-level judgment following the tool's algorithm
- Explain your rationale clearly"""

ROB_ASSESSMENT_USER = """Assess the risk of bias for this study using the {tool_name}.

Study Information:
Title: {title}
Authors: {authors}
Year: {year}

Study Text:
{study_text}

Domains to Assess:
{domains_description}

For each domain:
1. Answer each signaling question with evidence
2. Provide verbatim supporting quotes
3. Make a domain judgment based on the signaling question responses
4. Explain your rationale

Respond in JSON format:
{{
    "domain_assessments": {{
        "domain_name": {{
            "signaling_responses": [
                {{
                    "question_id": "...",
                    "question_text": "...",
                    "response": "Yes" | "Probably Yes" | "Probably No" | "No" | "No Information",
                    "supporting_quote": "Verbatim quote from text or null",
                    "notes": "Additional context if needed"
                }}
            ],
            "judgment": "low" | "some_concerns" | "high" | "moderate" | "serious" | "critical",
            "rationale": "Explanation based on signaling question responses",
            "supporting_quotes": ["List of key quotes supporting judgment"]
        }}
    }},
    "overall_judgment": "low" | "some_concerns" | "high" | "moderate" | "serious" | "critical",
    "overall_rationale": "Summary of overall risk of bias assessment"
}}"""

# =============================================================================
# ROB 2 SPECIFIC PROMPTS
# =============================================================================

ROB2_DOMAIN_GUIDANCE = """
Domain Assessment Guidance for RoB 2:

1. Randomization Process:
   - "Low Risk": Allocation was adequately randomized AND concealed, no concerning baseline imbalances
   - "Some Concerns": Information missing about randomization or concealment, OR small baseline imbalances
   - "High Risk": Allocation not random, not concealed, OR baseline imbalances suggest randomization problems

2. Deviations from Intended Interventions:
   - "Low Risk": Participants/personnel blinded OR deviations minimal and balanced
   - "Some Concerns": Some awareness but deviations minimal or balanced
   - "High Risk": Substantial unbalanced deviations affecting outcomes

3. Missing Outcome Data:
   - "Low Risk": Data available for (nearly) all participants OR appropriate handling
   - "Some Concerns": Moderate missingness without clear bias indication
   - "High Risk": Substantial missing data dependent on true values

4. Measurement of Outcome:
   - "Low Risk": Appropriate method, blinded assessors, OR objective outcome
   - "Some Concerns": Assessors may be aware but outcome relatively objective
   - "High Risk": Assessment likely influenced by knowledge of intervention

5. Selection of Reported Result:
   - "Low Risk": Pre-specified analysis plan followed, no selective reporting
   - "Some Concerns": No clear pre-specification but no selective reporting indication
   - "High Risk": Strong suspicion of result selection based on significance

Overall Judgment:
- "High Risk": ANY domain is High Risk
- "Some Concerns": No High Risk but ANY domain has Some Concerns
- "Low Risk": ALL domains are Low Risk
"""

# =============================================================================
# ROBINS-I SPECIFIC PROMPTS
# =============================================================================

ROBINS_I_DOMAIN_GUIDANCE = """
Domain Assessment Guidance for ROBINS-I:

Judgment levels: Low, Moderate, Serious, Critical, No Information

1. Confounding:
   - Consider whether important confounders were identified and controlled
   - Check for appropriate methods (regression, propensity scores, etc.)

2. Selection of Participants:
   - Consider selection based on post-intervention variables
   - Check if follow-up start and intervention start coincide

3. Classification of Interventions:
   - Ensure intervention groups clearly defined
   - Check if classification could be affected by outcome knowledge

4. Deviations from Intended Interventions:
   - Consider protocol deviations, co-interventions, treatment switches
   - Check if deviations were balanced and appropriately analyzed

5. Missing Data:
   - Check proportion with missing data
   - Consider if missingness is related to outcomes

6. Measurement of Outcomes:
   - Consider blinding and objectivity
   - Check if measurement methods were consistent across groups

7. Selection of Reported Result:
   - Check for pre-specified analysis plan
   - Consider selective reporting of subgroups or analyses

Overall Judgment follows worst domain:
Critical > Serious > Moderate > Low
"""

# =============================================================================
# QUADAS-2 SPECIFIC PROMPTS
# =============================================================================

QUADAS2_DOMAIN_GUIDANCE = """
Domain Assessment Guidance for QUADAS-2:

Each domain assesses both Risk of Bias and Applicability Concerns.

1. Patient Selection:
   - Risk of Bias: Consecutive/random sample? Case-control avoided? No inappropriate exclusions?
   - Applicability: Do patients match the review question?

2. Index Test:
   - Risk of Bias: Interpreted blind to reference standard? Threshold pre-specified?
   - Applicability: Does test conduct match review question?

3. Reference Standard:
   - Risk of Bias: Likely to correctly classify? Interpreted blind to index test?
   - Applicability: Does target condition definition match review question?

4. Flow and Timing:
   - Risk of Bias: Appropriate interval? Same reference standard for all? All patients included?
   - (No applicability assessment for this domain)

Judgments: Low, High, or Unclear

Overall Risk of Bias:
- "High": ANY domain is High
- "Unclear": No High but ANY domain is Unclear
- "Low": ALL domains are Low
"""

# =============================================================================
# NEWCASTLE-OTTAWA SCALE PROMPTS
# =============================================================================

NOS_ASSESSMENT_GUIDANCE = """
Newcastle-Ottawa Scale Assessment Guidance:

The NOS uses a star system (maximum 9 stars for cohort/case-control, 8 for cross-sectional).

When assessing, award stars based on specific criteria:

Selection (up to 4 stars):
- Representativeness of sample/cohort
- Selection of comparison group
- Ascertainment of exposure/case definition
- Outcome not present at start (cohort) / Definition of controls (case-control)

Comparability (up to 2 stars):
- Control for most important confounder (1 star)
- Control for additional confounder (1 star)

Outcome/Exposure (up to 3 stars):
- Assessment method
- Follow-up adequacy/Same method for cases and controls
- Follow-up completeness/Non-response rate

Quality Categories:
- 7-9 stars: Good quality (Low risk of bias)
- 4-6 stars: Fair quality (Some concerns)
- 0-3 stars: Poor quality (High risk of bias)
"""

# =============================================================================
# SINGLE DOMAIN ASSESSMENT PROMPT
# =============================================================================

SINGLE_DOMAIN_ASSESSMENT_USER = """Assess the following domain for this study:

Domain: {domain_name}
Description: {domain_description}

Signaling Questions:
{signaling_questions}

Study Text (relevant excerpt):
{study_text}

Provide your assessment for this domain only.

Respond in JSON format:
{{
    "signaling_responses": [
        {{
            "question_id": "...",
            "response": "...",
            "supporting_quote": "Verbatim quote or null",
            "notes": "..."
        }}
    ],
    "judgment": "low" | "some_concerns" | "high" | "moderate" | "serious" | "critical",
    "rationale": "Explanation based on signaling question responses",
    "confidence": 0.0 to 1.0,
    "supporting_quotes": ["Key quotes"]
}}"""

# =============================================================================
# OVERALL JUDGMENT CALCULATION PROMPT
# =============================================================================

OVERALL_JUDGMENT_USER = """Based on the domain-level judgments below, determine the overall
risk of bias for this study according to the {tool_name} algorithm.

Domain Judgments:
{domain_judgments}

Algorithm:
{overall_algorithm}

Respond in JSON format:
{{
    "overall_judgment": "low" | "some_concerns" | "high" | "moderate" | "serious" | "critical",
    "rationale": "Explanation of how domain judgments combine to overall judgment",
    "key_concerns": ["List of main concerns if not Low Risk"]
}}"""

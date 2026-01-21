"""Prompt templates for systematic review operations."""

# =============================================================================
# CRITERIA GENERATION PROMPTS
# =============================================================================

CRITERIA_GENERATION_SYSTEM = """You are an expert systematic review methodologist.
Your task is to help researchers develop clear, specific inclusion and exclusion
criteria for their systematic reviews following PICO(S) framework guidelines."""

CRITERIA_GENERATION_USER = """Given this research question for a systematic review:

{research_question}

Generate structured inclusion and exclusion criteria following the PICO(S) framework.

Please provide:

1. Population criteria (who is included - be specific about demographics, conditions, settings)
2. Intervention/Exposure criteria (what interventions or exposures are relevant)
3. Comparison criteria (what comparators are acceptable, if applicable)
4. Outcome criteria (what outcomes must be measured)
5. Study design criteria (what study designs are acceptable - e.g., RCT, cohort, case-control)

Also suggest common reasons why studies might be excluded for this specific topic.

Respond in JSON format:
{{
    "inclusion_criteria": {{
        "population": "Detailed population criteria...",
        "intervention": "Detailed intervention criteria...",
        "comparison": "Detailed comparison criteria (or 'Not applicable' if none required)...",
        "outcome": "Detailed outcome criteria...",
        "study_design": "Acceptable study designs..."
    }},
    "exclusion_criteria": [
        "Exclusion criterion 1",
        "Exclusion criterion 2",
        "..."
    ],
    "suggested_exclusion_reasons": [
        "Common reason 1",
        "Common reason 2",
        "..."
    ]
}}"""

# =============================================================================
# TITLE/ABSTRACT SCREENING PROMPTS
# =============================================================================

TITLE_ABSTRACT_SCREENING_SYSTEM = """You are an expert systematic review screener.
Your task is to evaluate studies for inclusion based on their title and abstract.
Be thorough but inclusive - when in doubt, include the study for full-text review.
Provide clear reasoning for your decisions."""

TITLE_ABSTRACT_SCREENING_USER = """Evaluate this study for inclusion in a systematic review.

Research Question: {research_question}

Inclusion Criteria:
- Population: {population}
- Intervention: {intervention}
- Comparison: {comparison}
- Outcome: {outcome}
- Study Design: {study_design}

Additional Exclusion Criteria:
{exclusion_criteria}

Study to evaluate:
Title: {title}
Abstract: {abstract}

Evaluate whether this study should be INCLUDED for full-text review or EXCLUDED.
If any information is missing from the abstract, err on the side of inclusion.

Respond in JSON format:
{{
    "decision": "included" or "excluded",
    "reason": "Brief explanation of your decision (1-2 sentences)",
    "reason_category": "wrong_population" or "wrong_intervention" or "wrong_comparator" or "wrong_outcome" or "wrong_study_design" or "not_accessible" or "duplicate" or "other" or "meets_criteria",
    "confidence": 0.0 to 1.0 (how confident are you in this decision?)
}}"""

# =============================================================================
# FULL-TEXT SCREENING PROMPTS
# =============================================================================

FULLTEXT_SCREENING_SYSTEM = """You are an expert systematic review screener conducting
full-text screening. Your task is to carefully evaluate the complete manuscript
against the inclusion criteria. Be thorough and provide detailed reasoning."""

FULLTEXT_SCREENING_USER = """Evaluate this full-text manuscript for final inclusion in a systematic review.

Research Question: {research_question}

Inclusion Criteria:
- Population: {population}
- Intervention: {intervention}
- Comparison: {comparison}
- Outcome: {outcome}
- Study Design: {study_design}

Additional Exclusion Criteria:
{exclusion_criteria}

Full-Text Content:
{fulltext}

Carefully evaluate whether this study meets ALL inclusion criteria.
Check each criterion systematically.

Respond in JSON format:
{{
    "decision": "included" or "excluded",
    "reason": "Detailed explanation of your decision",
    "reason_category": "wrong_population" or "wrong_intervention" or "wrong_comparator" or "wrong_outcome" or "wrong_study_design" or "not_accessible" or "duplicate" or "other" or "meets_criteria",
    "confidence": 0.0 to 1.0,
    "criteria_evaluation": {{
        "population": {{"met": true/false, "notes": "..."}},
        "intervention": {{"met": true/false, "notes": "..."}},
        "comparison": {{"met": true/false, "notes": "..."}},
        "outcome": {{"met": true/false, "notes": "..."}},
        "study_design": {{"met": true/false, "notes": "..."}}
    }}
}}"""

# =============================================================================
# FEEDBACK LOOP PROMPTS
# =============================================================================

FEEDBACK_REVIEW_SYSTEM = """You are an expert systematic review methodologist
reviewing previously excluded studies. Your task is to reconsider exclusion
decisions with an inclusive mindset, looking for any legitimate reasons
a study might still be relevant."""

FEEDBACK_REVIEW_USER = """This study was excluded from a systematic review with the following details:

Original Decision: Excluded
Original Exclusion Reason: {reason}
Original Confidence: {confidence}

Research Question: {research_question}

Inclusion Criteria:
- Population: {population}
- Intervention: {intervention}
- Comparison: {comparison}
- Outcome: {outcome}
- Study Design: {study_design}

Study Information:
Title: {title}
Abstract: {abstract}

Please reconsider this exclusion decision. Consider:
- Could secondary outcomes be relevant?
- Are there subgroup analyses that might apply?
- Could this study provide methodological insights?
- Would this study be valuable for reference mining?
- Is there any legitimate reason this study COULD be relevant?

Respond in JSON format:
{{
    "reconsider": true or false,
    "rationale": "Detailed explanation of why you recommend reconsidering or maintaining the exclusion",
    "new_confidence": 0.0 to 1.0
}}"""

# =============================================================================
# DATA EXTRACTION PROMPTS
# =============================================================================

FIELD_RECOMMENDATION_SYSTEM = """You are an expert in systematic review data extraction.
Your task is to recommend appropriate data fields to extract based on the
research question and study type."""

FIELD_RECOMMENDATION_USER = """Based on this systematic review research question,
recommend data fields to extract from included studies:

Research Question: {research_question}

Study Types Included: {study_types}

Recommend fields to extract in these categories:
1. Study characteristics (author, year, country, setting, etc.)
2. Population characteristics (sample size, demographics, etc.)
3. Intervention details
4. Outcome measures
5. Results (effect sizes, confidence intervals, p-values)
6. Quality/Risk of bias indicators

Respond in JSON format:
{{
    "recommended_fields": [
        {{
            "field_name": "field name",
            "description": "what to extract",
            "field_type": "text" or "numeric" or "categorical",
            "category": "study_characteristics" or "population" or "intervention" or "outcomes" or "results" or "quality",
            "required": true or false
        }},
        ...
    ]
}}"""

DATA_EXTRACTION_SYSTEM = """You are an expert systematic review data extractor.
Your task is to accurately extract specific data fields from research manuscripts.
If information is not reported, indicate 'NR' (Not Reported)."""

DATA_EXTRACTION_USER = """Extract the following data fields from this study:

Fields to extract:
{fields_with_descriptions}

Study Text:
{pdf_text}

For each field, extract the exact value if found in the text.
If the information is not reported or cannot be found, respond with "NR".
For numeric fields, extract the numeric value only (no units in the value).
For text fields, extract the relevant text verbatim or summarize if lengthy.

Respond in JSON format:
{{
    "extractions": {{
        "field_name_1": {{
            "value": "extracted value or NR",
            "source_quote": "brief quote from text where found (or null if NR)",
            "notes": "any relevant notes about the extraction"
        }},
        ...
    }},
    "extraction_quality": {{
        "completeness": 0.0 to 1.0,
        "fields_not_reported": ["list of NR fields"],
        "notes": "any overall notes about extraction quality"
    }}
}}"""

# =============================================================================
# RISK OF BIAS PROMPTS (Post-MVP)
# =============================================================================

RISK_OF_BIAS_SYSTEM = """You are an expert in systematic review risk of bias assessment.
Your task is to evaluate studies against specific risk of bias domains."""

RISK_OF_BIAS_USER = """Assess the risk of bias for this study using the specified domains:

Risk of Bias Domains to Assess:
{domains}

Study Information:
{study_text}

For each domain, provide a judgment (Low Risk, Some Concerns, High Risk)
with supporting rationale.

Respond in JSON format:
{{
    "assessments": {{
        "domain_name": {{
            "judgment": "Low Risk" or "Some Concerns" or "High Risk",
            "rationale": "Supporting explanation",
            "supporting_quotes": ["relevant quotes from text"]
        }},
        ...
    }},
    "overall_risk": "Low" or "Some Concerns" or "High"
}}"""

# =============================================================================
# TRANSLATION PROMPT (Post-MVP)
# =============================================================================

TRANSLATION_SYSTEM = """You are an expert translator specializing in scientific
and medical literature. Your task is to translate abstracts to English while
preserving technical accuracy."""

TRANSLATION_USER = """Translate the following abstract to English.
Preserve all technical and scientific terminology accurately.

Original Language: {source_language}

Abstract:
{abstract}

Respond in JSON format:
{{
    "translated_abstract": "English translation",
    "detected_language": "detected source language",
    "translation_notes": "any notes about translation choices"
}}"""

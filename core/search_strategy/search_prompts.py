"""Prompt templates for search strategy generation."""

# =============================================================================
# PICO ANALYSIS PROMPTS
# =============================================================================

PICO_ANALYSIS_SYSTEM = """You are an expert systematic review methodologist and medical librarian.
Your task is to analyze research questions and break them down into PICO elements with comprehensive
search terms, synonyms, and MeSH terms for building systematic review search strategies.

You have extensive knowledge of:
- PICO framework (Population, Intervention, Comparison, Outcome)
- Medical Subject Headings (MeSH) vocabulary
- Boolean search logic for literature databases
- Common synonyms and alternative terms in medical/scientific literature"""

PICO_ANALYSIS_USER = """Analyze the following research question and extract PICO elements with search terms:

Research Question: {research_question}

For each PICO element, provide:
1. A clear label describing the element
2. Primary terms (the main concepts)
3. Synonyms (alternative terms, abbreviations, related concepts)
4. MeSH terms (Medical Subject Headings where applicable)
5. Brief notes on search considerations

Respond in JSON format:
{{
    "population": {{
        "label": "Description of the population",
        "primary_terms": ["term1", "term2"],
        "synonyms": ["synonym1", "synonym2", "abbreviation1"],
        "mesh_terms": ["MeSH term 1", "MeSH term 2"],
        "notes": "Any notes about searching for this population"
    }},
    "intervention": {{
        "label": "Description of the intervention/exposure",
        "primary_terms": ["term1", "term2"],
        "synonyms": ["synonym1", "synonym2"],
        "mesh_terms": ["MeSH term 1"],
        "notes": "Notes about intervention terms"
    }},
    "comparison": {{
        "label": "Description of the comparison (if applicable)",
        "primary_terms": ["term1"],
        "synonyms": ["synonym1"],
        "mesh_terms": [],
        "notes": "May not be applicable for all questions"
    }},
    "outcome": {{
        "label": "Description of the outcome(s)",
        "primary_terms": ["term1", "term2"],
        "synonyms": ["synonym1"],
        "mesh_terms": ["MeSH term 1"],
        "notes": "Notes about outcome terms"
    }},
    "other_concepts": [
        {{
            "label": "Additional concept name",
            "primary_terms": ["term1"],
            "synonyms": ["synonym1"],
            "mesh_terms": [],
            "notes": "E.g., study design filters, geographic limits"
        }}
    ],
    "search_notes": "General notes about the search strategy, potential challenges, or recommendations"
}}

Be comprehensive but focused. Include commonly used abbreviations, British/American spelling variations,
and related terms that authors might use. For MeSH terms, include both broad and specific headings as appropriate."""


# =============================================================================
# PUBMED STRATEGY GENERATION PROMPTS
# =============================================================================

PUBMED_GENERATION_SYSTEM = """You are an expert medical librarian specializing in PubMed search strategy development.
You create precise, comprehensive search strategies following best practices for systematic reviews.

You are skilled at:
- Using proper PubMed syntax (field tags, Boolean operators, truncation)
- Combining MeSH terms with free-text searching
- Building search strings that are both sensitive and specific
- Using appropriate field tags ([tiab], [tw], [mh], etc.)
- Organizing complex searches with line numbers"""

PUBMED_GENERATION_USER = """Create a PubMed search strategy based on the following PICO elements:

{pico_elements}

Requirements:
1. Use numbered search lines (1., 2., 3., etc.)
2. Combine terms within each concept using OR
3. Combine concepts using AND
4. Use appropriate field tags:
   - [tiab] for title/abstract
   - [tw] for text word
   - [mh] for MeSH terms
   - [mh:noexp] for MeSH without explosion
5. Use truncation (*) appropriately for word variations
6. Group terms logically with parentheses

Format your response as a complete PubMed search strategy with numbered lines, like this:

1. term1[tiab] OR term2[tiab] OR "phrase term"[tiab]
2. "MeSH Term"[mh]
3. #1 OR #2
4. intervention1[tiab] OR intervention2[tiab]
5. "Intervention MeSH"[mh]
6. #4 OR #5
7. outcome1[tiab] OR outcome2[tiab]
8. #3 AND #6 AND #7

End with a final line that combines all concepts."""


# =============================================================================
# DATABASE TRANSLATION PROMPTS
# =============================================================================

DATABASE_TRANSLATION_SYSTEM = """You are an expert medical librarian who translates search strategies
between different literature databases. You understand the syntax differences between PubMed, SCOPUS,
Web of Science, Cochrane Library, EMBASE, and OVID Medline.

Key syntax differences you know:
- SCOPUS: Uses TITLE-ABS-KEY(), no MeSH, uses W/n for proximity
- Web of Science: Uses TS=, TI=, AB=, uses NEAR/n for proximity
- Cochrane: Similar to PubMed, uses [mh] and :ti,ab,kw
- EMBASE: Uses exp/, .mp., .ti,ab., Emtree terms instead of MeSH
- OVID: Uses exp, .mp., adj# for proximity, $ for truncation"""

DATABASE_TRANSLATION_USER = """Translate this PubMed search strategy to {target_database}:

PubMed Strategy:
{pubmed_strategy}

Target Database: {target_database}

Syntax rules for {target_database}:
{syntax_rules}

Translate the search maintaining:
1. The same logical structure (concepts combined with AND/OR)
2. Equivalent field searching
3. Appropriate controlled vocabulary (if available)
4. Proper truncation and wildcards for the target database

Return ONLY the translated search strategy, formatted with numbered lines appropriate for the target database."""


# =============================================================================
# SYNTAX VALIDATION PROMPTS
# =============================================================================

SYNTAX_VALIDATION_SYSTEM = """You are a search syntax validator for literature databases.
You check search strategies for syntax errors, unbalanced parentheses, invalid field tags,
and logical errors in Boolean operations.

You are familiar with:
- PubMed, SCOPUS, Web of Science, Cochrane, EMBASE, OVID syntax
- Common errors like unmatched quotes, invalid operators, wrong field tags
- Best practices for search strategy construction"""

SYNTAX_VALIDATION_USER = """Validate this {database} search strategy for syntax errors:

{search_strategy}

Check for:
1. Unbalanced parentheses or brackets
2. Invalid field tags for {database}
3. Incorrect Boolean operator usage (AND, OR, NOT)
4. Unmatched quotation marks
5. Invalid truncation or wildcard usage
6. Line reference errors (e.g., #5 when only 4 lines exist)
7. Empty search lines

Respond in JSON format:
{{
    "is_valid": true/false,
    "errors": [
        {{
            "line": 1,
            "error_type": "syntax_error",
            "message": "Description of the error",
            "suggestion": "How to fix it"
        }}
    ],
    "warnings": [
        {{
            "line": 2,
            "warning_type": "best_practice",
            "message": "Suggestion for improvement"
        }}
    ],
    "summary": "Overall assessment of the search strategy"
}}"""


# =============================================================================
# TERM SUGGESTION PROMPTS
# =============================================================================

TERM_SUGGESTION_SYSTEM = """You are an expert medical librarian who suggests additional search terms
and synonyms to improve systematic review search strategies. You have comprehensive knowledge of
medical terminology, common abbreviations, and alternative phrasings used in scientific literature."""

TERM_SUGGESTION_USER = """Given this concept for a systematic review search:

Concept: {concept_label}
Current terms: {current_terms}

Suggest additional terms that should be included to make the search comprehensive:
1. Synonyms
2. Related terms
3. Common abbreviations
4. British/American spelling variations
5. Historical or outdated terms still found in older literature
6. Relevant MeSH terms

Respond in JSON format:
{{
    "suggested_synonyms": ["term1", "term2"],
    "suggested_mesh_terms": ["MeSH 1", "MeSH 2"],
    "suggested_abbreviations": ["abbr1", "abbr2"],
    "spelling_variants": ["UK spelling", "US spelling"],
    "related_concepts": ["broader term", "narrower term"],
    "rationale": "Brief explanation of why these terms are important"
}}"""

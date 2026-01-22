"""Database syntax rules for search strategy translation."""

DATABASE_SYNTAX_RULES = {
    "PUBMED": {
        "name": "PubMed",
        "description": "NCBI PubMed/MEDLINE database",
        "field_tags": {
            "title_abstract": "[tiab]",
            "text_word": "[tw]",
            "mesh": "[mh]",
            "mesh_noexp": "[mh:noexp]",
            "title": "[ti]",
            "abstract": "[ab]",
            "author": "[au]",
            "journal": "[ta]",
            "publication_type": "[pt]",
            "subheading": "[sh]",
            "all_fields": "[All Fields]",
        },
        "boolean_operators": ["AND", "OR", "NOT"],
        "truncation": "*",
        "wildcard": None,
        "proximity": None,
        "phrase_quotes": True,
        "line_reference": "#",
        "notes": "MeSH terms are automatically exploded unless [mh:noexp] is used.",
        "example": '("diabetes mellitus"[mh] OR diabete*[tiab]) AND (metformin[tiab] OR "Metformin"[mh])',
    },
    "SCOPUS": {
        "name": "Scopus",
        "description": "Elsevier Scopus database",
        "field_tags": {
            "title_abstract_keyword": "TITLE-ABS-KEY()",
            "title": "TITLE()",
            "abstract": "ABS()",
            "keyword": "KEY()",
            "author": "AUTH()",
            "affiliation": "AFFIL()",
            "source_title": "SRCTITLE()",
            "all_fields": "ALL()",
        },
        "boolean_operators": ["AND", "OR", "AND NOT"],
        "truncation": "*",
        "wildcard": "?",
        "proximity": "W/n",  # Within n words
        "phrase_quotes": True,
        "line_reference": None,  # Uses parentheses grouping
        "notes": "No controlled vocabulary (MeSH). Use free-text terms only. W/n for proximity (e.g., pain W/3 chronic).",
        "example": 'TITLE-ABS-KEY("diabetes mellitus" OR diabete*) AND TITLE-ABS-KEY(metformin)',
    },
    "WOS": {
        "name": "Web of Science",
        "description": "Clarivate Web of Science Core Collection",
        "field_tags": {
            "topic": "TS=",
            "title": "TI=",
            "abstract": "AB=",
            "author_keywords": "AK=",
            "keywords_plus": "KP=",
            "author": "AU=",
            "publication_name": "SO=",
            "all_fields": "ALL=",
        },
        "boolean_operators": ["AND", "OR", "NOT"],
        "truncation": "*",
        "wildcard": "?",
        "proximity": "NEAR/n",  # Within n words, any order
        "phrase_quotes": True,
        "line_reference": "#",
        "notes": "No controlled vocabulary. TS= searches title, abstract, author keywords, and Keywords Plus. NEAR/n for proximity.",
        "example": 'TS=("diabetes mellitus" OR diabete*) AND TS=(metformin)',
    },
    "COCHRANE": {
        "name": "Cochrane Library",
        "description": "Cochrane Library (CENTRAL, CDSR)",
        "field_tags": {
            "title_abstract_keyword": ":ti,ab,kw",
            "title": ":ti",
            "abstract": ":ab",
            "keyword": ":kw",
            "mesh": "[mh]",
            "mesh_noexp": "[mh ^]",
            "all_text": ":pt",
        },
        "boolean_operators": ["AND", "OR", "NOT"],
        "truncation": "*",
        "wildcard": "?",
        "proximity": "NEAR/n",
        "phrase_quotes": True,
        "line_reference": "#",
        "notes": "Similar to PubMed syntax. MeSH terms available for CENTRAL searches. Use :ti,ab,kw for comprehensive text search.",
        "example": '("diabetes mellitus" OR diabete*):ti,ab,kw AND (metformin):ti,ab,kw',
    },
    "EMBASE": {
        "name": "EMBASE",
        "description": "Elsevier EMBASE (via Embase.com)",
        "field_tags": {
            "title_abstract": ".ti,ab.",
            "title": ".ti.",
            "abstract": ".ab.",
            "emtree_exploded": "exp",
            "emtree_focused": "/",
            "keyword": ".kw.",
            "multi_purpose": ".mp.",  # Searches multiple fields
            "device_trade_name": ".dv,tn.",
        },
        "boolean_operators": ["AND", "OR", "NOT"],
        "truncation": "*",
        "wildcard": "?",
        "proximity": "ADJ#",  # Adjacent within # words
        "phrase_quotes": True,
        "line_reference": None,  # Uses numbered lines
        "notes": "Uses Emtree controlled vocabulary instead of MeSH. exp for exploded terms, / for focused. ADJ# for proximity.",
        "example": "(exp diabetes mellitus/ OR diabete*.ti,ab.) AND (metformin.ti,ab. OR exp metformin/)",
    },
    "OVID": {
        "name": "OVID Medline",
        "description": "OVID Medline database",
        "field_tags": {
            "multi_purpose": ".mp.",
            "title_abstract": ".ti,ab.",
            "title": ".ti.",
            "abstract": ".ab.",
            "mesh_exploded": "exp",
            "mesh_focused": "/",
            "floating_subheading": ".fs.",
            "keyword_heading": ".kf.",
            "text_word": ".tw.",
        },
        "boolean_operators": ["and", "or", "not"],  # Lowercase in OVID
        "truncation": "$",  # Different from others!
        "wildcard": "?",
        "proximity": "adj#",  # Adjacent within # words
        "phrase_quotes": True,
        "line_reference": None,  # Uses numbered lines
        "notes": "Uses $ for truncation (not *). exp for exploded MeSH. adj# for proximity (e.g., adj3). Uses lowercase Boolean operators.",
        "example": "(exp diabetes mellitus/ or diabete$.ti,ab.) and (metformin.ti,ab. or exp metformin/)",
    },
}

# Database-specific instructions for AI translation
TRANSLATION_INSTRUCTIONS = {
    "SCOPUS": """
Key translation rules for SCOPUS:
1. Remove all MeSH terms - SCOPUS has no controlled vocabulary
2. Convert [tiab] to TITLE-ABS-KEY()
3. Keep truncation (*) the same
4. Use AND NOT instead of NOT
5. Group entire search in TITLE-ABS-KEY() or use separate field searches
6. Combine all free-text equivalents of MeSH terms into the search
""",
    "WOS": """
Key translation rules for Web of Science:
1. Remove all MeSH terms - WOS has no controlled vocabulary
2. Convert [tiab] to TS= (Topic) or TI= and AB= separately
3. Keep truncation (*) the same
4. Convert proximity to NEAR/n format
5. Combine all free-text equivalents of MeSH terms
""",
    "COCHRANE": """
Key translation rules for Cochrane Library:
1. MeSH terms can be kept - Cochrane uses MeSH
2. Convert [tiab] to :ti,ab,kw
3. Convert [mh] to [mh] (same format)
4. Convert [mh:noexp] to [mh ^]
5. Keep truncation (*) the same
""",
    "EMBASE": """
Key translation rules for EMBASE:
1. Convert MeSH terms to equivalent Emtree terms where possible
2. Convert [tiab] to .ti,ab.
3. Use exp for exploded Emtree terms
4. Convert truncation * to * (same)
5. Use ADJ# for proximity instead of NEAR
""",
    "OVID": """
Key translation rules for OVID Medline:
1. Convert truncation * to $
2. Convert [tiab] to .ti,ab.
3. Convert [mh] to exp term/ or term/
4. Use lowercase Boolean operators (and, or, not)
5. Use adj# for proximity
6. Format: term.ti,ab. not term[tiab]
""",
}

# Common study design filters by database
STUDY_FILTERS = {
    "PUBMED": {
        "rct": '("randomized controlled trial"[pt] OR "controlled clinical trial"[pt] OR randomized[tiab] OR randomised[tiab] OR placebo[tiab] OR "drug therapy"[sh] OR randomly[tiab] OR trial[tiab] OR groups[tiab])',
        "systematic_review": '("systematic review"[pt] OR "meta-analysis"[pt] OR "systematic review"[tiab] OR "meta-analysis"[tiab] OR metaanalysis[tiab])',
        "cohort": '("cohort studies"[mh] OR cohort[tiab] OR "longitudinal studies"[mh] OR "follow-up studies"[mh] OR prospective[tiab] OR retrospective[tiab])',
    },
    "COCHRANE": {
        "rct": '(randomized:ti,ab,kw OR randomised:ti,ab,kw OR placebo:ti,ab,kw OR randomly:ti,ab,kw)',
    },
}

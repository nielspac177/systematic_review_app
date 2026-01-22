"""Pydantic data models for systematic review application."""

from datetime import datetime
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field
import uuid


class ExclusionCategory(str, Enum):
    """PICO-based exclusion categories."""
    WRONG_POPULATION = "wrong_population"
    WRONG_INTERVENTION = "wrong_intervention"
    WRONG_COMPARATOR = "wrong_comparator"
    WRONG_OUTCOME = "wrong_outcome"
    WRONG_STUDY_DESIGN = "wrong_study_design"
    NOT_ACCESSIBLE = "not_accessible"
    DUPLICATE = "duplicate"
    OTHER = "other"
    MEETS_CRITERIA = "meets_criteria"  # For included studies


class ReviewType(str, Enum):
    """Types of systematic reviews supported."""
    STANDARD = "standard"  # Full PRISMA 2020
    RAPID = "rapid"  # Streamlined rapid review
    SCOPING = "scoping"  # Scoping review


class ScreeningPhase(str, Enum):
    """Phases of the screening process."""
    TITLE_ABSTRACT = "title_abstract"
    FULLTEXT = "fulltext"


class FieldType(str, Enum):
    """Data types for extraction fields."""
    TEXT = "text"
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    DATE = "date"
    BOOLEAN = "boolean"


# =============================================================================
# CRITERIA MODELS
# =============================================================================

class InclusionCriteria(BaseModel):
    """PICO-based inclusion criteria."""
    population: str = Field(..., description="Population criteria")
    intervention: str = Field(..., description="Intervention/exposure criteria")
    comparison: str = Field(default="Not applicable", description="Comparison criteria")
    outcome: str = Field(..., description="Outcome criteria")
    study_design: str = Field(..., description="Acceptable study designs")


class ReviewCriteria(BaseModel):
    """Complete review criteria."""
    inclusion: InclusionCriteria
    exclusion: list[str] = Field(default_factory=list, description="Exclusion criteria")
    suggested_exclusion_reasons: list[str] = Field(
        default_factory=list,
        description="Suggested common exclusion reasons"
    )


# =============================================================================
# STUDY MODELS
# =============================================================================

class Study(BaseModel):
    """A study to be screened."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pmid: Optional[str] = None
    doi: Optional[str] = None
    title: str
    abstract: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_text: Optional[str] = None
    source_database: Optional[str] = None  # PubMed, Embase, etc.
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ScreeningDecision(BaseModel):
    """Decision from screening process."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    phase: ScreeningPhase
    decision: Literal["included", "excluded"]
    reason: str = Field(..., description="Brief explanation of decision")
    reason_category: ExclusionCategory
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    criteria_evaluation: Optional[dict] = None  # For full-text screening
    created_at: datetime = Field(default_factory=datetime.now)

    # Feedback review fields
    feedback_reviewed: bool = False
    feedback_reconsider: Optional[bool] = None
    feedback_rationale: Optional[str] = None
    feedback_new_confidence: Optional[float] = None
    feedback_final_decision: Optional[Literal["included", "excluded"]] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# EXTRACTION MODELS
# =============================================================================

class ExtractionField(BaseModel):
    """Definition of a data extraction field."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    field_name: str
    description: str
    field_type: FieldType
    category: str  # study_characteristics, population, intervention, outcomes, results, quality
    required: bool = False
    display_order: int = 0
    options: Optional[list[str]] = None  # For categorical fields


class ExtractedValue(BaseModel):
    """Single extracted data value."""
    field_name: str
    value: Optional[str] = None
    is_not_reported: bool = False
    source_quote: Optional[str] = None
    notes: Optional[str] = None
    source: Literal["llm", "manual"] = "llm"
    confidence: Optional[float] = None


class StudyExtraction(BaseModel):
    """All extracted data for a single study."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    extractions: dict[str, ExtractedValue]
    extraction_quality: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# PROJECT MODELS
# =============================================================================

class PRISMACounts(BaseModel):
    """PRISMA 2020 flow diagram counts."""
    # Identification
    records_identified_databases: int = 0
    records_identified_registers: int = 0
    records_removed_duplicates: int = 0

    # Screening
    records_screened: int = 0
    records_excluded_screening: int = 0

    # Eligibility
    reports_sought: int = 0
    reports_not_retrieved: int = 0
    reports_assessed: int = 0
    reports_excluded: int = 0

    # Included
    studies_included: int = 0

    # Exclusion reasons breakdown
    exclusion_reasons: dict[str, int] = Field(default_factory=dict)


class Project(BaseModel):
    """A systematic review project."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    research_question: str
    review_type: ReviewType = ReviewType.STANDARD
    criteria: Optional[ReviewCriteria] = None

    # LLM configuration
    llm_provider: Optional[str] = None  # "openai" or "anthropic"
    llm_model: Optional[str] = None

    # Budget
    budget_limit: Optional[float] = None

    # Storage
    storage_path: str

    # Extraction fields
    extraction_fields: list[ExtractionField] = Field(default_factory=list)

    # PRISMA counts
    prisma_counts: PRISMACounts = Field(default_factory=PRISMACounts)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Status
    current_phase: Optional[str] = None  # Track which phase user is on

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# AUDIT MODELS
# =============================================================================

class AuditEntry(BaseModel):
    """Single audit log entry for an LLM call."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    study_id: Optional[str] = None
    operation: str
    prompt: str
    response: str
    decision: Optional[str] = None
    confidence: Optional[float] = None
    input_tokens: int
    output_tokens: int
    cost: float
    model: str
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# RISK OF BIAS MODELS
# =============================================================================

class RoBToolType(str, Enum):
    """Supported Risk of Bias assessment tools."""
    ROB_2 = "rob_2"                         # Cochrane RoB 2 for RCTs
    ROBINS_I = "robins_i"                   # Non-randomized interventional
    NEWCASTLE_OTTAWA_COHORT = "nos_cohort"
    NEWCASTLE_OTTAWA_CASE_CONTROL = "nos_case_control"
    NEWCASTLE_OTTAWA_CROSS_SECTIONAL = "nos_cross_sectional"
    QUADAS_2 = "quadas_2"                   # Diagnostic accuracy
    JBI_RCT = "jbi_rct"
    JBI_COHORT = "jbi_cohort"
    JBI_QUALITATIVE = "jbi_qualitative"
    CUSTOM = "custom"


class JudgmentLevel(str, Enum):
    """Standardized judgment levels across tools."""
    LOW = "low"
    SOME_CONCERNS = "some_concerns"
    MODERATE = "moderate"                   # ROBINS-I
    SERIOUS = "serious"                     # ROBINS-I
    CRITICAL = "critical"                   # ROBINS-I
    HIGH = "high"
    UNCLEAR = "unclear"
    NOT_APPLICABLE = "not_applicable"
    NO_INFORMATION = "no_information"


class SignalingQuestion(BaseModel):
    """Individual signaling question within a domain."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_text: str
    guidance: Optional[str] = None
    response_options: list[str] = Field(
        default_factory=lambda: ["Yes", "Probably Yes", "Probably No", "No", "No Information"]
    )


class RoBDomainTemplate(BaseModel):
    """Enhanced domain definition with signaling questions."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    short_name: str
    description: str
    signaling_questions: list[SignalingQuestion] = Field(default_factory=list)
    judgment_guidance: dict[str, str] = Field(default_factory=dict)
    display_order: int = 0


class RoBTemplate(BaseModel):
    """Complete RoB tool template definition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_type: RoBToolType
    name: str
    version: str = "1.0"
    description: str
    applicable_study_designs: list[str] = Field(default_factory=list)
    domains: list[RoBDomainTemplate] = Field(default_factory=list)
    overall_judgment_algorithm: Optional[str] = None
    is_builtin: bool = True
    is_customized: bool = False

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SignalingQuestionResponse(BaseModel):
    """Response to a signaling question."""
    question_id: str
    response: str
    supporting_quote: Optional[str] = None
    notes: Optional[str] = None


class RoBDomainJudgment(BaseModel):
    """Enhanced judgment for a single domain."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str
    domain_name: str
    signaling_responses: list[SignalingQuestionResponse] = Field(default_factory=list)
    judgment: JudgmentLevel
    rationale: str
    supporting_quotes: list[str] = Field(default_factory=list)
    ai_suggested_judgment: Optional[JudgmentLevel] = None
    ai_confidence: Optional[float] = None
    is_ai_generated: bool = True
    is_human_verified: bool = False
    is_flagged_uncertain: bool = False
    human_override_notes: Optional[str] = None


class StudyRoBAssessment(BaseModel):
    """Complete RoB assessment for a single study."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    template_id: str
    tool_type: RoBToolType
    detected_study_design: Optional[str] = None
    comparison_label: Optional[str] = None  # For multi-arm trials
    domain_judgments: list[RoBDomainJudgment] = Field(default_factory=list)
    overall_judgment: JudgmentLevel
    overall_rationale: str = ""
    ai_cost: float = 0.0
    ai_model: Optional[str] = None
    assessor_id: Optional[str] = None
    reviewer_id: Optional[str] = None       # For dual review
    assessment_status: str = "draft"        # draft, submitted, reviewed, finalized
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class RoBProjectSettings(BaseModel):
    """Project-level RoB configuration."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    enabled_tools: list[RoBToolType] = Field(default_factory=list)
    dual_review_enabled: bool = False
    auto_detect_study_design: bool = True
    require_supporting_quotes: bool = True
    flag_uncertain_threshold: float = 0.7
    batch_queue: list[str] = Field(default_factory=list)
    batch_status: str = "idle"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class RoBAuditEntry(BaseModel):
    """Audit entry for AI vs human edit tracking."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_id: str
    study_id: str
    action: str  # "ai_generated", "human_edit", "human_verify", "reviewer_edit"
    domain_id: Optional[str] = None
    previous_judgment: Optional[str] = None
    new_judgment: Optional[str] = None
    user_id: Optional[str] = None
    notes: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# Legacy models preserved for backwards compatibility
class RoBDomain(BaseModel):
    """Risk of bias domain definition (legacy)."""
    name: str
    description: str
    signaling_questions: list[str] = Field(default_factory=list)


class RoBJudgment(BaseModel):
    """Risk of bias judgment for a single domain (legacy)."""
    domain: str
    judgment: Literal["Low Risk", "Some Concerns", "High Risk"]
    rationale: str
    supporting_quotes: list[str] = Field(default_factory=list)


class StudyRoB(BaseModel):
    """Risk of bias assessment for a study (legacy)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    assessments: list[RoBJudgment]
    overall_risk: Literal["Low", "Some Concerns", "High"]
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# =============================================================================
# SEARCH STRATEGY MODELS
# =============================================================================

class PICOElement(BaseModel):
    """A PICO element with terms and synonyms."""
    element_type: Literal["population", "intervention", "comparison", "outcome", "other"]
    label: str
    primary_terms: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    mesh_terms: list[str] = Field(default_factory=list)
    notes: str = ""


class ConceptBlock(BaseModel):
    """A concept block for search strategy building."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    pico_element: PICOElement
    boolean_operator: Literal["OR"] = "OR"


class SearchStrategy(BaseModel):
    """Search strategy for a systematic review."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    research_question: str
    pico_analysis: Optional[dict] = None
    concept_blocks: list[ConceptBlock] = Field(default_factory=list)
    pubmed_strategy: Optional[str] = None
    scopus_strategy: Optional[str] = None
    wos_strategy: Optional[str] = None
    cochrane_strategy: Optional[str] = None
    embase_strategy: Optional[str] = None
    ovid_strategy: Optional[str] = None
    validation_errors: dict[str, list[str]] = Field(default_factory=dict)
    pubmed_history: list[str] = Field(default_factory=list)  # For undo/redo
    pubmed_history_index: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ParsedReference(BaseModel):
    """A reference parsed from RIS/NBIB file."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_file: str
    source_database: str
    title: str
    abstract: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    duplicate_reason: Optional[str] = None  # "doi", "title_fuzzy", "title_author_year"
    duplicate_score: Optional[float] = None


class DeduplicationResult(BaseModel):
    """Results from deduplication process."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    records_per_source: dict[str, int] = Field(default_factory=dict)
    total_records: int = 0
    unique_records: int = 0
    duplicate_count: int = 0
    doi_duplicates: int = 0
    title_fuzzy_duplicates: int = 0
    title_author_year_duplicates: int = 0
    all_references: list[ParsedReference] = Field(default_factory=list)


class WizardState(BaseModel):
    """State for the Search Strategy Wizard."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: Optional[str] = None
    current_step: int = 1
    completed_steps: list[int] = Field(default_factory=list)
    research_question: str = ""
    existing_pubmed_strategy: Optional[str] = None
    search_strategy: Optional[SearchStrategy] = None
    deduplication_result: Optional[DeduplicationResult] = None
    selected_databases: list[str] = Field(default_factory=lambda: ["SCOPUS", "WOS"])
    reviewed_duplicates: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

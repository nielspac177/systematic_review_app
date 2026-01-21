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
# RISK OF BIAS MODELS (Post-MVP)
# =============================================================================

class RoBDomain(BaseModel):
    """Risk of bias domain definition."""
    name: str
    description: str
    signaling_questions: list[str] = Field(default_factory=list)


class RoBJudgment(BaseModel):
    """Risk of bias judgment for a single domain."""
    domain: str
    judgment: Literal["Low Risk", "Some Concerns", "High Risk"]
    rationale: str
    supporting_quotes: list[str] = Field(default_factory=list)


class StudyRoB(BaseModel):
    """Risk of bias assessment for a study."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    assessments: list[RoBJudgment]
    overall_risk: Literal["Low", "Some Concerns", "High"]
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

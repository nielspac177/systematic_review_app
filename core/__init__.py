"""Core module for systematic review application."""

from .llm import (
    BaseLLMClient,
    OpenAIClient,
    AnthropicClient,
    get_llm_client,
    CostTracker,
    OperationType,
)
from .storage import (
    SessionManager,
    AuditLogger,
    Project,
    Study,
    ScreeningDecision,
    ExtractionField,
    StudyExtraction,
    ReviewCriteria,
    PRISMACounts,
)
from .screening import (
    CriteriaGenerator,
    TitleAbstractScreener,
    FulltextScreener,
    FeedbackReviewer,
)
from .extraction import (
    FieldRecommender,
    DataExtractor,
)
from .pdf import (
    PDFProcessor,
    PDFBatchProcessor,
)

__all__ = [
    # LLM
    "BaseLLMClient",
    "OpenAIClient",
    "AnthropicClient",
    "get_llm_client",
    "CostTracker",
    "OperationType",
    # Storage
    "SessionManager",
    "AuditLogger",
    "Project",
    "Study",
    "ScreeningDecision",
    "ExtractionField",
    "StudyExtraction",
    "ReviewCriteria",
    "PRISMACounts",
    # Screening
    "CriteriaGenerator",
    "TitleAbstractScreener",
    "FulltextScreener",
    "FeedbackReviewer",
    # Extraction
    "FieldRecommender",
    "DataExtractor",
    # PDF
    "PDFProcessor",
    "PDFBatchProcessor",
]

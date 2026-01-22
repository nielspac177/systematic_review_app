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
from .storage.models import (
    PICOElement,
    ConceptBlock,
    SearchStrategy,
    ParsedReference,
    DeduplicationResult,
    WizardState,
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
from .search_strategy import (
    PICOAnalyzer,
    ConceptBuilder,
    PubMedGenerator,
    DatabaseTranslator,
    SyntaxValidator,
)
from .file_parsers import (
    RISParser,
    NBIBParser,
    Deduplicator,
)
from .export import (
    DOCXGenerator,
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
    # Search Strategy Models
    "PICOElement",
    "ConceptBlock",
    "SearchStrategy",
    "ParsedReference",
    "DeduplicationResult",
    "WizardState",
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
    # Search Strategy
    "PICOAnalyzer",
    "ConceptBuilder",
    "PubMedGenerator",
    "DatabaseTranslator",
    "SyntaxValidator",
    # File Parsers
    "RISParser",
    "NBIBParser",
    "Deduplicator",
    # Export
    "DOCXGenerator",
]

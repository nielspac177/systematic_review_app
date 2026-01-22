"""Application settings and configuration."""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass
class LLMSettings:
    """LLM provider settings."""
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_default_model: str = "gpt-4o"

    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_default_model: str = "claude-sonnet-4-20250514"

    # Defaults
    default_temperature: float = 0.3
    default_max_tokens: int = 1000


@dataclass
class ScreeningSettings:
    """Screening configuration."""
    # Confidence thresholds
    low_confidence_threshold: float = 0.8
    auto_include_threshold: float = 0.95

    # Batch processing
    batch_size: int = 50
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class ExtractionSettings:
    """Data extraction configuration."""
    # Text limits
    max_text_chars: int = 50000

    # OCR settings
    ocr_enabled: bool = True
    ocr_dpi: int = 200


@dataclass
class StorageSettings:
    """Storage configuration."""
    default_storage_path: str = field(
        default_factory=lambda: str(Path.home() / "systematic_reviews")
    )
    database_name: str = "project.db"


@dataclass
class UISettings:
    """UI configuration."""
    page_title: str = "Systematic Review App"
    page_icon: str = "📚"
    layout: str = "wide"


@dataclass
class Settings:
    """Application settings container."""
    llm: LLMSettings = field(default_factory=LLMSettings)
    screening: ScreeningSettings = field(default_factory=ScreeningSettings)
    extraction: ExtractionSettings = field(default_factory=ExtractionSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    ui: UISettings = field(default_factory=UISettings)

    # App info
    app_name: str = "Systematic Review App"
    version: str = "1.0.0"
    debug: bool = False

    def __post_init__(self):
        """Load settings from environment variables."""
        self._load_from_env()

    def _load_from_env(self):
        """Load settings from environment variables."""
        # LLM API keys
        if os.getenv("OPENAI_API_KEY"):
            self.llm.openai_api_key = os.getenv("OPENAI_API_KEY")

        if os.getenv("ANTHROPIC_API_KEY"):
            self.llm.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        # Debug mode
        if os.getenv("DEBUG"):
            self.debug = os.getenv("DEBUG").lower() in ("true", "1", "yes")

        # Storage path
        if os.getenv("STORAGE_PATH"):
            self.storage.default_storage_path = os.getenv("STORAGE_PATH")


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()


# Model pricing information
MODEL_PRICING = {
    # OpenAI GPT-5 series (per 1M tokens)
    "gpt-5.2-pro": {"input": 15.00, "output": 60.00},
    "gpt-5.2": {"input": 10.00, "output": 40.00},
    "gpt-5": {"input": 8.00, "output": 32.00},
    "gpt-5-mini": {"input": 1.00, "output": 4.00},
    "gpt-5-nano": {"input": 0.25, "output": 1.00},
    # OpenAI GPT-4 series (per 1M tokens)
    "gpt-4.1": {"input": 6.00, "output": 18.00},
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},

    # Anthropic Claude 4 series (per 1M tokens)
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    # Anthropic Claude 3.7 series
    "claude-3-7-sonnet-latest": {"input": 3.00, "output": 15.00},
    # Anthropic Claude 3.5 series
    "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-latest": {"input": 0.80, "output": 4.00},
    # Anthropic Claude 3 series
    "claude-3-opus-latest": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}


# Default extraction fields by review type
DEFAULT_REVIEW_TYPES = {
    "standard": {
        "name": "Standard Systematic Review",
        "description": "Full PRISMA 2020 compliant review",
        "phases": ["title_abstract", "fulltext", "extraction"],
        "feedback_enabled": True,
    },
    "rapid": {
        "name": "Rapid Review",
        "description": "Streamlined review for quick turnaround",
        "phases": ["title_abstract", "extraction"],
        "feedback_enabled": False,
    },
    "scoping": {
        "name": "Scoping Review",
        "description": "Broad review to map available evidence",
        "phases": ["title_abstract", "charting"],
        "feedback_enabled": False,
    },
}


# PICO exclusion categories
EXCLUSION_CATEGORIES = {
    "wrong_population": "Study population does not match criteria",
    "wrong_intervention": "Intervention/exposure does not match criteria",
    "wrong_comparator": "Comparator does not match criteria",
    "wrong_outcome": "Outcomes do not match criteria",
    "wrong_study_design": "Study design not acceptable",
    "not_accessible": "Full text not accessible",
    "duplicate": "Duplicate publication",
    "other": "Other reason",
}

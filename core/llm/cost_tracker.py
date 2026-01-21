"""Cost tracking and budget management for LLM operations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class OperationType(str, Enum):
    """Types of LLM operations for cost tracking."""
    CRITERIA_GENERATION = "criteria_generation"
    TITLE_ABSTRACT_SCREENING = "title_abstract_screening"
    FULLTEXT_SCREENING = "fulltext_screening"
    FEEDBACK_REVIEW = "feedback_review"
    FIELD_RECOMMENDATION = "field_recommendation"
    DATA_EXTRACTION = "data_extraction"
    RISK_OF_BIAS = "risk_of_bias"
    TRANSLATION = "translation"
    OTHER = "other"


@dataclass
class CostEntry:
    """Single cost tracking entry."""
    operation: OperationType
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: datetime
    study_id: Optional[str] = None
    model: str = ""
    notes: str = ""


@dataclass
class CostEstimate:
    """Cost estimate for an operation."""
    operation: OperationType
    n_items: int
    avg_input_tokens: int
    avg_output_tokens: int
    estimated_cost: float
    model: str


class BudgetExceededError(Exception):
    """Raised when budget limit is exceeded."""
    def __init__(self, current_cost: float, budget_limit: float, operation: str):
        self.current_cost = current_cost
        self.budget_limit = budget_limit
        self.operation = operation
        super().__init__(
            f"Budget exceeded during {operation}. "
            f"Current: ${current_cost:.4f}, Limit: ${budget_limit:.2f}"
        )


class CostTracker:
    """Track costs and manage budget limits for LLM operations."""

    # Average token estimates for different operations
    TOKEN_ESTIMATES = {
        OperationType.CRITERIA_GENERATION: {"input": 200, "output": 500},
        OperationType.TITLE_ABSTRACT_SCREENING: {"input": 500, "output": 100},
        OperationType.FULLTEXT_SCREENING: {"input": 4000, "output": 300},
        OperationType.FEEDBACK_REVIEW: {"input": 600, "output": 150},
        OperationType.FIELD_RECOMMENDATION: {"input": 300, "output": 400},
        OperationType.DATA_EXTRACTION: {"input": 3000, "output": 500},
        OperationType.RISK_OF_BIAS: {"input": 3000, "output": 400},
        OperationType.TRANSLATION: {"input": 500, "output": 500},
    }

    def __init__(self, budget_limit: Optional[float] = None):
        """
        Initialize cost tracker.

        Args:
            budget_limit: Optional maximum budget in USD. If set, operations
                         will raise BudgetExceededError when exceeded.
        """
        self.budget_limit = budget_limit
        self.entries: list[CostEntry] = []
        self._paused = False

    @property
    def total_cost(self) -> float:
        """Get total cost of all tracked operations."""
        return sum(e.cost for e in self.entries)

    @property
    def remaining_budget(self) -> Optional[float]:
        """Get remaining budget, or None if no limit set."""
        if self.budget_limit is None:
            return None
        return max(0, self.budget_limit - self.total_cost)

    @property
    def is_paused(self) -> bool:
        """Check if tracking is paused due to budget concerns."""
        return self._paused

    def set_budget_limit(self, limit: float) -> None:
        """Set or update the budget limit."""
        self.budget_limit = limit
        self._paused = False

    def estimate_cost(
        self,
        llm_client,
        operation: OperationType,
        n_items: int = 1,
        avg_input_tokens: Optional[int] = None,
        avg_output_tokens: Optional[int] = None,
    ) -> CostEstimate:
        """
        Estimate cost for an operation before running.

        Args:
            llm_client: LLM client to use for cost calculation
            operation: Type of operation
            n_items: Number of items to process
            avg_input_tokens: Override default input token estimate
            avg_output_tokens: Override default output token estimate

        Returns:
            CostEstimate with breakdown
        """
        defaults = self.TOKEN_ESTIMATES.get(
            operation,
            {"input": 500, "output": 200}
        )

        input_tokens = avg_input_tokens or defaults["input"]
        output_tokens = avg_output_tokens or defaults["output"]

        total_input = input_tokens * n_items
        total_output = output_tokens * n_items

        estimated_cost = llm_client.estimate_cost(total_input, total_output)

        return CostEstimate(
            operation=operation,
            n_items=n_items,
            avg_input_tokens=input_tokens,
            avg_output_tokens=output_tokens,
            estimated_cost=estimated_cost,
            model=llm_client.model,
        )

    def add_cost(
        self,
        operation: OperationType,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        study_id: Optional[str] = None,
        model: str = "",
        notes: str = "",
        check_budget: bool = True,
    ) -> bool:
        """
        Add a cost entry.

        Args:
            operation: Type of operation
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            cost: Actual cost in USD
            study_id: Optional study identifier
            model: Model used
            notes: Optional notes
            check_budget: If True, raise error if budget exceeded

        Returns:
            True if cost was added successfully, False if budget would be exceeded

        Raises:
            BudgetExceededError: If check_budget=True and budget exceeded
        """
        new_total = self.total_cost + cost

        if self.budget_limit is not None and new_total > self.budget_limit:
            self._paused = True
            if check_budget:
                raise BudgetExceededError(new_total, self.budget_limit, operation.value)
            return False

        entry = CostEntry(
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            timestamp=datetime.now(),
            study_id=study_id,
            model=model,
            notes=notes,
        )
        self.entries.append(entry)
        return True

    def get_summary(self) -> dict:
        """
        Get cost breakdown summary.

        Returns:
            Dictionary with cost breakdown by operation
        """
        summary = {
            "total_cost": self.total_cost,
            "budget_limit": self.budget_limit,
            "remaining_budget": self.remaining_budget,
            "total_entries": len(self.entries),
            "total_input_tokens": sum(e.input_tokens for e in self.entries),
            "total_output_tokens": sum(e.output_tokens for e in self.entries),
            "by_operation": {},
        }

        for op_type in OperationType:
            op_entries = [e for e in self.entries if e.operation == op_type]
            if op_entries:
                summary["by_operation"][op_type.value] = {
                    "count": len(op_entries),
                    "total_cost": sum(e.cost for e in op_entries),
                    "total_input_tokens": sum(e.input_tokens for e in op_entries),
                    "total_output_tokens": sum(e.output_tokens for e in op_entries),
                }

        return summary

    def get_entries_for_study(self, study_id: str) -> list[CostEntry]:
        """Get all cost entries for a specific study."""
        return [e for e in self.entries if e.study_id == study_id]

    def get_entries_for_operation(self, operation: OperationType) -> list[CostEntry]:
        """Get all cost entries for a specific operation type."""
        return [e for e in self.entries if e.operation == operation]

    def reset(self) -> None:
        """Reset all tracking data."""
        self.entries.clear()
        self._paused = False

    def to_dict(self) -> dict:
        """Serialize tracker state to dictionary."""
        return {
            "budget_limit": self.budget_limit,
            "entries": [
                {
                    "operation": e.operation.value,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "cost": e.cost,
                    "timestamp": e.timestamp.isoformat(),
                    "study_id": e.study_id,
                    "model": e.model,
                    "notes": e.notes,
                }
                for e in self.entries
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CostTracker":
        """Deserialize tracker state from dictionary."""
        tracker = cls(budget_limit=data.get("budget_limit"))
        for entry_data in data.get("entries", []):
            entry = CostEntry(
                operation=OperationType(entry_data["operation"]),
                input_tokens=entry_data["input_tokens"],
                output_tokens=entry_data["output_tokens"],
                cost=entry_data["cost"],
                timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                study_id=entry_data.get("study_id"),
                model=entry_data.get("model", ""),
                notes=entry_data.get("notes", ""),
            )
            tracker.entries.append(entry)
        return tracker

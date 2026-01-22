"""Search syntax validation for various databases."""

import re
import json
from typing import Optional
from dataclasses import dataclass

from ..llm.cost_tracker import CostTracker, OperationType
from .search_prompts import SYNTAX_VALIDATION_SYSTEM, SYNTAX_VALIDATION_USER


@dataclass
class ValidationError:
    """A syntax validation error."""
    line: int
    error_type: str
    message: str
    suggestion: str = ""


@dataclass
class ValidationWarning:
    """A syntax validation warning."""
    line: int
    warning_type: str
    message: str


@dataclass
class ValidationResult:
    """Result of syntax validation."""
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
    summary: str


class SyntaxValidator:
    """Validate search syntax for literature databases."""

    # Valid field tags by database
    VALID_FIELD_TAGS = {
        "PUBMED": [
            "[tiab]", "[tw]", "[mh]", "[mh:noexp]", "[ti]", "[ab]",
            "[au]", "[ta]", "[pt]", "[sh]", "[all fields]", "[mesh]",
        ],
        "SCOPUS": [
            "TITLE-ABS-KEY", "TITLE", "ABS", "KEY", "AUTH",
            "AFFIL", "SRCTITLE", "ALL",
        ],
        "WOS": [
            "TS=", "TI=", "AB=", "AK=", "KP=", "AU=", "SO=", "ALL=",
        ],
        "COCHRANE": [
            ":ti,ab,kw", ":ti", ":ab", ":kw", "[mh]", "[mh ^]", ":pt",
        ],
        "EMBASE": [
            ".ti,ab.", ".ti.", ".ab.", ".kw.", ".mp.", ".dv,tn.",
            "exp", "/",
        ],
        "OVID": [
            ".mp.", ".ti,ab.", ".ti.", ".ab.", ".fs.", ".kf.", ".tw.",
            "exp", "/", "adj",
        ],
    }

    def __init__(
        self,
        llm_client=None,
        cost_tracker: Optional[CostTracker] = None,
    ):
        """
        Initialize syntax validator.

        Args:
            llm_client: Optional LLM client for advanced validation
            cost_tracker: Optional cost tracker
        """
        self.llm_client = llm_client
        self.cost_tracker = cost_tracker

    def validate(self, strategy: str, database: str = "PUBMED") -> ValidationResult:
        """
        Validate a search strategy.

        Args:
            strategy: The search strategy to validate
            database: Target database (PUBMED, SCOPUS, WOS, COCHRANE, EMBASE, OVID)

        Returns:
            ValidationResult with errors, warnings, and summary
        """
        errors = []
        warnings = []

        # Basic syntax checks
        errors.extend(self._check_parentheses(strategy))
        errors.extend(self._check_quotes(strategy))
        errors.extend(self._check_boolean_operators(strategy, database))
        errors.extend(self._check_line_references(strategy))

        # Database-specific checks
        if database.upper() in self.VALID_FIELD_TAGS:
            errors.extend(self._check_field_tags(strategy, database))

        # Warnings
        warnings.extend(self._check_best_practices(strategy, database))

        is_valid = len(errors) == 0

        summary = self._generate_summary(strategy, errors, warnings, database)

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            summary=summary,
        )

    def validate_with_llm(self, strategy: str, database: str = "PUBMED") -> ValidationResult:
        """
        Validate using LLM for more comprehensive analysis.

        Args:
            strategy: The search strategy to validate
            database: Target database

        Returns:
            ValidationResult with detailed feedback
        """
        if not self.llm_client:
            return self.validate(strategy, database)

        # First do basic validation
        basic_result = self.validate(strategy, database)

        # Then use LLM for deeper analysis
        prompt = SYNTAX_VALIDATION_USER.format(
            database=database,
            search_strategy=strategy,
        )

        messages = [
            {"role": "system", "content": SYNTAX_VALIDATION_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_client.chat(
            messages=messages,
            temperature=0.2,
            max_tokens=1000,
            json_mode=True,
        )

        try:
            llm_result = json.loads(response.content)
        except json.JSONDecodeError:
            # Fall back to basic result
            return basic_result

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.SYNTAX_VALIDATION,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
                notes=f"Syntax validation for {database}",
            )

        # Merge results
        errors = basic_result.errors.copy()
        warnings = basic_result.warnings.copy()

        # Add LLM-detected errors
        for err in llm_result.get("errors", []):
            errors.append(ValidationError(
                line=err.get("line", 0),
                error_type=err.get("error_type", "llm_detected"),
                message=err.get("message", ""),
                suggestion=err.get("suggestion", ""),
            ))

        # Add LLM-detected warnings
        for warn in llm_result.get("warnings", []):
            warnings.append(ValidationWarning(
                line=warn.get("line", 0),
                warning_type=warn.get("warning_type", "llm_suggestion"),
                message=warn.get("message", ""),
            ))

        return ValidationResult(
            is_valid=llm_result.get("is_valid", len(errors) == 0),
            errors=errors,
            warnings=warnings,
            summary=llm_result.get("summary", basic_result.summary),
        )

    def _check_parentheses(self, strategy: str) -> list[ValidationError]:
        """Check for balanced parentheses."""
        errors = []
        lines = strategy.split("\n")

        for i, line in enumerate(lines, 1):
            count = 0
            for char in line:
                if char == "(":
                    count += 1
                elif char == ")":
                    count -= 1
                if count < 0:
                    errors.append(ValidationError(
                        line=i,
                        error_type="unbalanced_parentheses",
                        message="Unmatched closing parenthesis",
                        suggestion="Check that all parentheses are properly paired",
                    ))
                    break

            if count > 0:
                errors.append(ValidationError(
                    line=i,
                    error_type="unbalanced_parentheses",
                    message=f"Unmatched opening parenthesis ({count} unclosed)",
                    suggestion="Add closing parenthesis",
                ))

        return errors

    def _check_quotes(self, strategy: str) -> list[ValidationError]:
        """Check for balanced quotation marks."""
        errors = []
        lines = strategy.split("\n")

        for i, line in enumerate(lines, 1):
            # Count double quotes
            double_count = line.count('"')
            if double_count % 2 != 0:
                errors.append(ValidationError(
                    line=i,
                    error_type="unbalanced_quotes",
                    message="Odd number of quotation marks",
                    suggestion="Ensure all phrases are properly quoted",
                ))

        return errors

    def _check_boolean_operators(self, strategy: str, database: str) -> list[ValidationError]:
        """Check for valid Boolean operator usage."""
        errors = []
        lines = strategy.split("\n")

        # Get expected case for database
        lowercase_db = database.upper() == "OVID"

        for i, line in enumerate(lines, 1):
            # Skip empty lines and line number prefixes
            content = re.sub(r'^\d+\.\s*', '', line.strip())
            if not content:
                continue

            # Check for operator at start or end (excluding line refs)
            if not re.match(r'^#\d+', content):
                if re.match(r'^(AND|OR|NOT)\s', content, re.IGNORECASE):
                    errors.append(ValidationError(
                        line=i,
                        error_type="operator_position",
                        message="Boolean operator at start of search line",
                        suggestion="Remove leading operator or check line structure",
                    ))

            if re.search(r'\s(AND|OR|NOT)$', content, re.IGNORECASE):
                errors.append(ValidationError(
                    line=i,
                    error_type="operator_position",
                    message="Boolean operator at end of search line",
                    suggestion="Add search term after operator",
                ))

            # Check for double operators
            if re.search(r'(AND|OR|NOT)\s+(AND|OR|NOT)', content, re.IGNORECASE):
                errors.append(ValidationError(
                    line=i,
                    error_type="double_operator",
                    message="Consecutive Boolean operators",
                    suggestion="Remove one of the operators",
                ))

        return errors

    def _check_line_references(self, strategy: str) -> list[ValidationError]:
        """Check for valid line references."""
        errors = []
        lines = strategy.split("\n")

        # Find all defined line numbers
        defined_lines = set()
        for line in lines:
            match = re.match(r'^(\d+)\.\s', line.strip())
            if match:
                defined_lines.add(int(match.group(1)))

        # Check references
        for i, line in enumerate(lines, 1):
            refs = re.findall(r'#(\d+)', line)
            for ref in refs:
                ref_num = int(ref)
                if ref_num not in defined_lines:
                    errors.append(ValidationError(
                        line=i,
                        error_type="invalid_reference",
                        message=f"Reference to undefined line #{ref_num}",
                        suggestion=f"Define line {ref_num} or update reference",
                    ))
                # Check for self-reference
                current_line_match = re.match(r'^(\d+)\.\s', line.strip())
                if current_line_match and int(current_line_match.group(1)) == ref_num:
                    errors.append(ValidationError(
                        line=i,
                        error_type="self_reference",
                        message=f"Line references itself (#{ref_num})",
                        suggestion="Remove self-reference",
                    ))

        return errors

    def _check_field_tags(self, strategy: str, database: str) -> list[ValidationError]:
        """Check for valid field tags for the database."""
        errors = []
        valid_tags = self.VALID_FIELD_TAGS.get(database.upper(), [])

        if not valid_tags:
            return errors

        lines = strategy.split("\n")

        for i, line in enumerate(lines, 1):
            # Extract field tags from line
            if database.upper() == "PUBMED":
                tags = re.findall(r'\[([^\]]+)\]', line)
                for tag in tags:
                    tag_with_brackets = f"[{tag.lower()}]"
                    if tag_with_brackets not in [t.lower() for t in valid_tags]:
                        errors.append(ValidationError(
                            line=i,
                            error_type="invalid_field_tag",
                            message=f"Unknown field tag: [{tag}]",
                            suggestion=f"Valid PubMed tags: {', '.join(valid_tags[:5])}...",
                        ))

        return errors

    def _check_best_practices(self, strategy: str, database: str) -> list[ValidationWarning]:
        """Check for best practice recommendations."""
        warnings = []
        lines = strategy.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for very long lines
            if len(line) > 500:
                warnings.append(ValidationWarning(
                    line=i,
                    warning_type="long_line",
                    message="Very long search line - consider splitting into multiple lines",
                ))

            # Check for potential truncation issues
            if database.upper() == "PUBMED":
                # Warn about short truncation
                short_trunc = re.findall(r'\b(\w{1,2})\*', line)
                for term in short_trunc:
                    warnings.append(ValidationWarning(
                        line=i,
                        warning_type="short_truncation",
                        message=f"Short truncation '{term}*' may retrieve too many results",
                    ))

            # Check for missing field tags in PubMed
            if database.upper() == "PUBMED":
                # Find terms without field tags
                words = re.findall(r'\b([a-zA-Z]+)\b(?!\[)', line)
                # Filter out Boolean operators and common words
                skip_words = {"AND", "OR", "NOT", "exp", "adj"}
                untagged = [w for w in words if w.upper() not in skip_words and len(w) > 2]
                if untagged and "#" not in line:  # Not a combination line
                    warnings.append(ValidationWarning(
                        line=i,
                        warning_type="missing_field_tag",
                        message="Some terms may be missing field tags (e.g., [tiab])",
                    ))

        return warnings

    def _generate_summary(
        self,
        strategy: str,
        errors: list[ValidationError],
        warnings: list[ValidationWarning],
        database: str,
    ) -> str:
        """Generate a summary of validation results."""
        lines = strategy.split("\n")
        line_count = len([l for l in lines if l.strip()])

        if not errors and not warnings:
            return f"Search strategy is valid. {line_count} lines checked for {database}."
        elif not errors:
            return f"Search strategy is valid with {len(warnings)} suggestion(s). {line_count} lines."
        else:
            return f"Found {len(errors)} error(s) and {len(warnings)} warning(s) in {line_count} lines."

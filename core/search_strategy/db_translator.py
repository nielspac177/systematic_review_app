"""Database translation for search strategies."""

import json
import re
from typing import Optional

from ..llm.cost_tracker import CostTracker, OperationType
from ..storage.audit_logger import AuditLogger
from .search_prompts import DATABASE_TRANSLATION_SYSTEM, DATABASE_TRANSLATION_USER
from config.database_syntax import DATABASE_SYNTAX_RULES, TRANSLATION_INSTRUCTIONS


class DatabaseTranslator:
    """Translate search strategies between literature databases."""

    SUPPORTED_DATABASES = ["SCOPUS", "WOS", "COCHRANE", "EMBASE", "OVID"]

    def __init__(
        self,
        llm_client,
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize database translator.

        Args:
            llm_client: LLM client for translation
            cost_tracker: Optional cost tracker
            audit_logger: Optional audit logger
            project_id: Optional project ID for logging
        """
        self.llm_client = llm_client
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.project_id = project_id

    def translate(self, pubmed_strategy: str, target_database: str) -> str:
        """
        Translate a PubMed search strategy to another database.

        Args:
            pubmed_strategy: PubMed search strategy
            target_database: Target database (SCOPUS, WOS, COCHRANE, EMBASE, OVID)

        Returns:
            Translated search strategy
        """
        target_db = target_database.upper()
        if target_db not in self.SUPPORTED_DATABASES:
            raise ValueError(f"Unsupported database: {target_database}")

        # Get syntax rules for target database
        syntax_rules = self._get_syntax_rules(target_db)

        prompt = DATABASE_TRANSLATION_USER.format(
            pubmed_strategy=pubmed_strategy,
            target_database=target_db,
            syntax_rules=syntax_rules,
        )

        messages = [
            {"role": "system", "content": DATABASE_TRANSLATION_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )

        translated = response.content.strip()

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.DATABASE_TRANSLATION,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
                notes=f"Translation to {target_db}",
            )

        # Log audit trail
        if self.audit_logger and self.project_id:
            self.audit_logger.log_operation(
                project_id=self.project_id,
                operation="database_translation",
                prompt=prompt,
                response=response.content,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        return translated

    def translate_all(self, pubmed_strategy: str, databases: Optional[list[str]] = None) -> dict[str, str]:
        """
        Translate a PubMed strategy to multiple databases.

        Args:
            pubmed_strategy: PubMed search strategy
            databases: List of target databases (default: all supported)

        Returns:
            Dictionary mapping database name to translated strategy
        """
        if databases is None:
            databases = self.SUPPORTED_DATABASES

        translations = {}
        for db in databases:
            db_upper = db.upper()
            if db_upper in self.SUPPORTED_DATABASES:
                translations[db_upper] = self.translate(pubmed_strategy, db_upper)

        return translations

    def quick_translate(self, pubmed_strategy: str, target_database: str) -> str:
        """
        Quick translation using rule-based approach (no LLM).

        This is faster but less accurate than LLM translation.
        Useful for previews or when LLM is unavailable.

        Args:
            pubmed_strategy: PubMed search strategy
            target_database: Target database

        Returns:
            Translated search strategy
        """
        target_db = target_database.upper()

        if target_db == "SCOPUS":
            return self._translate_to_scopus(pubmed_strategy)
        elif target_db == "WOS":
            return self._translate_to_wos(pubmed_strategy)
        elif target_db == "COCHRANE":
            return self._translate_to_cochrane(pubmed_strategy)
        elif target_db == "EMBASE":
            return self._translate_to_embase(pubmed_strategy)
        elif target_db == "OVID":
            return self._translate_to_ovid(pubmed_strategy)
        else:
            raise ValueError(f"Unsupported database: {target_database}")

    def _get_syntax_rules(self, database: str) -> str:
        """Get syntax rules for a database as a formatted string."""
        rules = DATABASE_SYNTAX_RULES.get(database, {})
        instructions = TRANSLATION_INSTRUCTIONS.get(database, "")

        formatted = []
        formatted.append(f"Database: {rules.get('name', database)}")
        formatted.append(f"Description: {rules.get('description', '')}")

        if rules.get("field_tags"):
            formatted.append("\nField Tags:")
            for name, tag in rules["field_tags"].items():
                formatted.append(f"  - {name}: {tag}")

        formatted.append(f"\nBoolean Operators: {', '.join(rules.get('boolean_operators', ['AND', 'OR', 'NOT']))}")
        formatted.append(f"Truncation: {rules.get('truncation', '*')}")
        formatted.append(f"Wildcard: {rules.get('wildcard', '?')}")
        formatted.append(f"Proximity: {rules.get('proximity', 'N/A')}")

        if rules.get("notes"):
            formatted.append(f"\nNotes: {rules['notes']}")

        if instructions:
            formatted.append(f"\n{instructions}")

        return "\n".join(formatted)

    def _translate_to_scopus(self, strategy: str) -> str:
        """Rule-based translation to SCOPUS."""
        translated = []

        for line in strategy.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Remove line numbers for processing
            match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if match:
                line_num = match.group(1)
                content = match.group(2)
            else:
                continue

            # Skip MeSH-only lines (no equivalent in SCOPUS)
            if re.match(r'^"[^"]+"$$mh(:\w+)?$$\s*$', content):
                continue

            # Convert field tags
            content = re.sub(r'\[(tiab|tw|ti|ab)\]', '', content)
            content = re.sub(r'"([^"]+)"\[mh(:\w+)?\]', r'"\1"', content)

            # Remove empty OR groups after removing MeSH
            content = re.sub(r'\s+OR\s+OR\s+', ' OR ', content)
            content = re.sub(r'^\s*OR\s+', '', content)
            content = re.sub(r'\s+OR\s*$', '', content)

            # Wrap in TITLE-ABS-KEY if not a combination line
            if "#" not in content and content.strip():
                content = f"TITLE-ABS-KEY({content})"

            if content.strip():
                translated.append(f"{line_num}. {content}")

        return "\n".join(translated)

    def _translate_to_wos(self, strategy: str) -> str:
        """Rule-based translation to Web of Science."""
        translated = []

        for line in strategy.split("\n"):
            line = line.strip()
            if not line:
                continue

            match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if match:
                line_num = match.group(1)
                content = match.group(2)
            else:
                continue

            # Remove MeSH terms (no equivalent)
            content = re.sub(r'"[^"]+"\[mh(:\w+)?\]\s*(OR\s+)?', '', content)

            # Convert field tags
            content = re.sub(r'\[(tiab|tw)\]', '', content)
            content = re.sub(r'\[ti\]', '', content)
            content = re.sub(r'\[ab\]', '', content)

            # Clean up
            content = re.sub(r'\s+OR\s+OR\s+', ' OR ', content)
            content = re.sub(r'^\s*OR\s+', '', content)
            content = re.sub(r'\s+OR\s*$', '', content)

            # Wrap with TS= if not a combination line
            if "#" not in content and content.strip():
                content = f"TS=({content})"

            if content.strip():
                translated.append(f"{line_num}. {content}")

        return "\n".join(translated)

    def _translate_to_cochrane(self, strategy: str) -> str:
        """Rule-based translation to Cochrane Library."""
        translated = []

        for line in strategy.split("\n"):
            line = line.strip()
            if not line:
                continue

            match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if match:
                line_num = match.group(1)
                content = match.group(2)
            else:
                continue

            # Convert field tags
            content = re.sub(r'\[tiab\]', ':ti,ab,kw', content)
            content = re.sub(r'\[tw\]', ':ti,ab,kw', content)
            content = re.sub(r'\[ti\]', ':ti', content)
            content = re.sub(r'\[ab\]', ':ab', content)
            # MeSH stays similar
            content = re.sub(r'\[mh:noexp\]', '[mh ^]', content)

            if content.strip():
                translated.append(f"{line_num}. {content}")

        return "\n".join(translated)

    def _translate_to_embase(self, strategy: str) -> str:
        """Rule-based translation to EMBASE."""
        translated = []

        for line in strategy.split("\n"):
            line = line.strip()
            if not line:
                continue

            match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if match:
                line_num = match.group(1)
                content = match.group(2)
            else:
                continue

            # Convert field tags
            content = re.sub(r'\[tiab\]', '.ti,ab.', content)
            content = re.sub(r'\[tw\]', '.mp.', content)
            content = re.sub(r'\[ti\]', '.ti.', content)
            content = re.sub(r'\[ab\]', '.ab.', content)

            # Convert MeSH to Emtree format (simplified)
            content = re.sub(r'"([^"]+)"\[mh\]', r'exp \1/', content)
            content = re.sub(r'"([^"]+)"\[mh:noexp\]', r'\1/', content)

            if content.strip():
                translated.append(f"{line_num}. {content}")

        return "\n".join(translated)

    def _translate_to_ovid(self, strategy: str) -> str:
        """Rule-based translation to OVID Medline."""
        translated = []

        for line in strategy.split("\n"):
            line = line.strip()
            if not line:
                continue

            match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if match:
                line_num = match.group(1)
                content = match.group(2)
            else:
                continue

            # Convert truncation * to $
            content = re.sub(r'\*', '$', content)

            # Convert field tags
            content = re.sub(r'\[tiab\]', '.ti,ab.', content)
            content = re.sub(r'\[tw\]', '.tw.', content)
            content = re.sub(r'\[ti\]', '.ti.', content)
            content = re.sub(r'\[ab\]', '.ab.', content)

            # Convert MeSH
            content = re.sub(r'"([^"]+)"\[mh\]', r'exp \1/', content)
            content = re.sub(r'"([^"]+)"\[mh:noexp\]', r'\1/', content)

            # Convert Boolean to lowercase
            content = re.sub(r'\bAND\b', 'and', content)
            content = re.sub(r'\bOR\b', 'or', content)
            content = re.sub(r'\bNOT\b', 'not', content)

            if content.strip():
                translated.append(f"{line_num}. {content}")

        return "\n".join(translated)

    @staticmethod
    def get_database_info(database: str) -> dict:
        """Get information about a database."""
        return DATABASE_SYNTAX_RULES.get(database.upper(), {})

    @staticmethod
    def get_supported_databases() -> list[str]:
        """Get list of supported target databases."""
        return DatabaseTranslator.SUPPORTED_DATABASES.copy()

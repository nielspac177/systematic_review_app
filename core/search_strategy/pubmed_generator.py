"""PubMed search strategy generation."""

import json
import re
from typing import Optional

from ..storage.models import ConceptBlock
from ..llm.cost_tracker import CostTracker, OperationType
from ..storage.audit_logger import AuditLogger
from .search_prompts import PUBMED_GENERATION_SYSTEM, PUBMED_GENERATION_USER


class PubMedGenerator:
    """Generate PubMed search strategies from concept blocks."""

    def __init__(
        self,
        llm_client,
        cost_tracker: Optional[CostTracker] = None,
        audit_logger: Optional[AuditLogger] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize PubMed generator.

        Args:
            llm_client: LLM client for generation
            cost_tracker: Optional cost tracker
            audit_logger: Optional audit logger
            project_id: Optional project ID for logging
        """
        self.llm_client = llm_client
        self.cost_tracker = cost_tracker
        self.audit_logger = audit_logger
        self.project_id = project_id

    def generate(self, concept_blocks: list[ConceptBlock]) -> str:
        """
        Generate a PubMed search strategy from concept blocks.

        Args:
            concept_blocks: List of concept blocks with terms

        Returns:
            PubMed search strategy as a string
        """
        # Format PICO elements for prompt
        pico_text = self._format_concept_blocks(concept_blocks)

        prompt = PUBMED_GENERATION_USER.format(pico_elements=pico_text)

        messages = [
            {"role": "system", "content": PUBMED_GENERATION_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )

        strategy = response.content.strip()

        # Track cost
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.PUBMED_GENERATION,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
                notes="PubMed strategy generation",
            )

        # Log audit trail
        if self.audit_logger and self.project_id:
            self.audit_logger.log_operation(
                project_id=self.project_id,
                operation="pubmed_generation",
                prompt=prompt,
                response=response.content,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
            )

        return strategy

    def generate_from_terms(
        self,
        population_terms: Optional[list[str]] = None,
        intervention_terms: Optional[list[str]] = None,
        comparison_terms: Optional[list[str]] = None,
        outcome_terms: Optional[list[str]] = None,
        other_terms: Optional[dict[str, list[str]]] = None,
    ) -> str:
        """
        Generate a basic PubMed search strategy from term lists.

        This is a deterministic generation without LLM, useful for quick previews.

        Args:
            population_terms: Population search terms
            intervention_terms: Intervention search terms
            comparison_terms: Comparison search terms
            outcome_terms: Outcome search terms
            other_terms: Dictionary of other concept names to term lists

        Returns:
            PubMed search strategy as a string
        """
        lines = []
        line_num = 1
        concept_refs = {}

        def format_terms(terms: list[str]) -> str:
            """Format a list of terms for PubMed search."""
            formatted = []
            for term in terms:
                term = term.strip()
                if not term:
                    continue
                # Check if it's a MeSH term (contains [mh])
                if "[mh]" in term.lower() or "[mesh]" in term.lower():
                    formatted.append(term)
                # Phrase (contains space)
                elif " " in term:
                    formatted.append(f'"{term}"[tiab]')
                else:
                    # Single word with truncation if appropriate
                    if term.endswith("*"):
                        formatted.append(f"{term}[tiab]")
                    else:
                        formatted.append(f"{term}[tiab]")
            return " OR ".join(formatted) if formatted else ""

        # Population
        if population_terms:
            pop_search = format_terms(population_terms)
            if pop_search:
                lines.append(f"{line_num}. {pop_search}")
                concept_refs["population"] = line_num
                line_num += 1

        # Intervention
        if intervention_terms:
            int_search = format_terms(intervention_terms)
            if int_search:
                lines.append(f"{line_num}. {int_search}")
                concept_refs["intervention"] = line_num
                line_num += 1

        # Comparison
        if comparison_terms:
            comp_search = format_terms(comparison_terms)
            if comp_search:
                lines.append(f"{line_num}. {comp_search}")
                concept_refs["comparison"] = line_num
                line_num += 1

        # Outcome
        if outcome_terms:
            out_search = format_terms(outcome_terms)
            if out_search:
                lines.append(f"{line_num}. {out_search}")
                concept_refs["outcome"] = line_num
                line_num += 1

        # Other concepts
        if other_terms:
            for concept_name, terms in other_terms.items():
                other_search = format_terms(terms)
                if other_search:
                    lines.append(f"{line_num}. {other_search}")
                    concept_refs[concept_name] = line_num
                    line_num += 1

        # Final combination line
        if concept_refs:
            refs = [f"#{ref}" for ref in concept_refs.values()]
            lines.append(f"{line_num}. {' AND '.join(refs)}")

        return "\n".join(lines)

    def _format_concept_blocks(self, concept_blocks: list[ConceptBlock]) -> str:
        """Format concept blocks for the LLM prompt."""
        formatted = []

        for block in concept_blocks:
            elem = block.pico_element
            section = [f"## {block.name} ({elem.element_type.upper()})"]
            section.append(f"Label: {elem.label}")

            if elem.primary_terms:
                section.append(f"Primary terms: {', '.join(elem.primary_terms)}")
            if elem.synonyms:
                section.append(f"Synonyms: {', '.join(elem.synonyms)}")
            if elem.mesh_terms:
                section.append(f"MeSH terms: {', '.join(elem.mesh_terms)}")
            if elem.notes:
                section.append(f"Notes: {elem.notes}")

            formatted.append("\n".join(section))

        return "\n\n".join(formatted)

    def optimize_strategy(self, strategy: str) -> str:
        """
        Optimize an existing PubMed search strategy.

        Args:
            strategy: Current search strategy

        Returns:
            Optimized search strategy
        """
        prompt = f"""Review and optimize this PubMed search strategy:

{strategy}

Improvements to consider:
1. Add appropriate truncation where word variations exist
2. Ensure MeSH terms are properly formatted with [mh]
3. Check for redundant terms
4. Verify line references are correct
5. Ensure balanced parentheses

Return the optimized search strategy maintaining the numbered line format."""

        messages = [
            {"role": "system", "content": PUBMED_GENERATION_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_client.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )

        if self.cost_tracker:
            self.cost_tracker.add_cost(
                operation=OperationType.PUBMED_GENERATION,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                model=response.model,
                notes="PubMed strategy optimization",
            )

        return response.content.strip()

    @staticmethod
    def parse_strategy_lines(strategy: str) -> list[dict]:
        """
        Parse a PubMed search strategy into structured lines.

        Args:
            strategy: PubMed search strategy string

        Returns:
            List of dictionaries with line number, content, and type
        """
        lines = []
        for line in strategy.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Match numbered lines: "1. search terms" or "#1 search terms"
            match = re.match(r'^(\d+)[.\s]+(.+)$', line)
            if match:
                line_num = int(match.group(1))
                content = match.group(2).strip()

                # Determine line type
                line_type = "search"
                if re.match(r'^#\d+(\s+(AND|OR|NOT)\s+#\d+)+', content):
                    line_type = "combination"

                lines.append({
                    "line_number": line_num,
                    "content": content,
                    "type": line_type,
                })

        return lines

    @staticmethod
    def extract_terms(strategy: str) -> list[str]:
        """
        Extract all search terms from a PubMed strategy.

        Args:
            strategy: PubMed search strategy string

        Returns:
            List of unique terms
        """
        terms = set()

        # Extract quoted phrases
        quoted = re.findall(r'"([^"]+)"', strategy)
        terms.update(quoted)

        # Extract terms with field tags
        tagged = re.findall(r'(\w+(?:\*)?)\[(tiab|mh|tw|ti|ab)\]', strategy, re.IGNORECASE)
        terms.update(t[0] for t in tagged)

        # Extract MeSH terms
        mesh = re.findall(r'"([^"]+)"\[mh(?::noexp)?\]', strategy, re.IGNORECASE)
        terms.update(mesh)

        return sorted(list(terms))

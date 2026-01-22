"""Concept block management for search strategy building."""

from typing import Optional
from ..storage.models import ConceptBlock, PICOElement


class ConceptBuilder:
    """Manage and manipulate concept blocks for search strategies."""

    def __init__(self, concept_blocks: Optional[list[ConceptBlock]] = None):
        """
        Initialize concept builder.

        Args:
            concept_blocks: Initial list of concept blocks
        """
        self.concept_blocks = concept_blocks or []

    def add_block(self, block: ConceptBlock) -> None:
        """Add a new concept block."""
        self.concept_blocks.append(block)

    def remove_block(self, block_id: str) -> bool:
        """
        Remove a concept block by ID.

        Args:
            block_id: ID of the block to remove

        Returns:
            True if removed, False if not found
        """
        for i, block in enumerate(self.concept_blocks):
            if block.id == block_id:
                self.concept_blocks.pop(i)
                return True
        return False

    def get_block(self, block_id: str) -> Optional[ConceptBlock]:
        """Get a concept block by ID."""
        for block in self.concept_blocks:
            if block.id == block_id:
                return block
        return None

    def update_block(self, block_id: str, **kwargs) -> bool:
        """
        Update a concept block.

        Args:
            block_id: ID of the block to update
            **kwargs: Fields to update

        Returns:
            True if updated, False if not found
        """
        block = self.get_block(block_id)
        if not block:
            return False

        for key, value in kwargs.items():
            if hasattr(block, key):
                setattr(block, key, value)
            elif hasattr(block.pico_element, key):
                setattr(block.pico_element, key, value)

        return True

    def add_term_to_block(
        self,
        block_id: str,
        term: str,
        term_type: str = "primary",
    ) -> bool:
        """
        Add a term to a concept block.

        Args:
            block_id: ID of the block
            term: Term to add
            term_type: Type of term (primary, synonym, mesh)

        Returns:
            True if added, False if not found
        """
        block = self.get_block(block_id)
        if not block:
            return False

        term = term.strip()
        if not term:
            return False

        if term_type == "primary":
            if term not in block.pico_element.primary_terms:
                block.pico_element.primary_terms.append(term)
        elif term_type == "synonym":
            if term not in block.pico_element.synonyms:
                block.pico_element.synonyms.append(term)
        elif term_type == "mesh":
            if term not in block.pico_element.mesh_terms:
                block.pico_element.mesh_terms.append(term)
        else:
            return False

        return True

    def remove_term_from_block(
        self,
        block_id: str,
        term: str,
        term_type: str = "primary",
    ) -> bool:
        """
        Remove a term from a concept block.

        Args:
            block_id: ID of the block
            term: Term to remove
            term_type: Type of term (primary, synonym, mesh)

        Returns:
            True if removed, False if not found
        """
        block = self.get_block(block_id)
        if not block:
            return False

        if term_type == "primary":
            if term in block.pico_element.primary_terms:
                block.pico_element.primary_terms.remove(term)
                return True
        elif term_type == "synonym":
            if term in block.pico_element.synonyms:
                block.pico_element.synonyms.remove(term)
                return True
        elif term_type == "mesh":
            if term in block.pico_element.mesh_terms:
                block.pico_element.mesh_terms.remove(term)
                return True

        return False

    def get_all_terms(self, block_id: str) -> dict:
        """
        Get all terms from a concept block.

        Args:
            block_id: ID of the block

        Returns:
            Dictionary with primary_terms, synonyms, mesh_terms
        """
        block = self.get_block(block_id)
        if not block:
            return {"primary_terms": [], "synonyms": [], "mesh_terms": []}

        return {
            "primary_terms": block.pico_element.primary_terms.copy(),
            "synonyms": block.pico_element.synonyms.copy(),
            "mesh_terms": block.pico_element.mesh_terms.copy(),
        }

    def create_new_block(
        self,
        name: str,
        element_type: str = "other",
        label: str = "",
        primary_terms: Optional[list[str]] = None,
        synonyms: Optional[list[str]] = None,
        mesh_terms: Optional[list[str]] = None,
        notes: str = "",
    ) -> ConceptBlock:
        """
        Create a new concept block.

        Args:
            name: Name of the block
            element_type: PICO element type
            label: Label for the element
            primary_terms: Primary search terms
            synonyms: Synonym terms
            mesh_terms: MeSH terms
            notes: Notes about the concept

        Returns:
            New ConceptBlock
        """
        pico_element = PICOElement(
            element_type=element_type,
            label=label or name,
            primary_terms=primary_terms or [],
            synonyms=synonyms or [],
            mesh_terms=mesh_terms or [],
            notes=notes,
        )

        block = ConceptBlock(
            name=name,
            pico_element=pico_element,
        )

        self.concept_blocks.append(block)
        return block

    def reorder_blocks(self, block_ids: list[str]) -> bool:
        """
        Reorder concept blocks.

        Args:
            block_ids: List of block IDs in desired order

        Returns:
            True if reordered, False if any ID not found
        """
        # Verify all IDs exist
        id_to_block = {block.id: block for block in self.concept_blocks}
        if not all(bid in id_to_block for bid in block_ids):
            return False

        # Reorder
        self.concept_blocks = [id_to_block[bid] for bid in block_ids]
        return True

    def merge_blocks(
        self,
        source_block_id: str,
        target_block_id: str,
        delete_source: bool = True,
    ) -> bool:
        """
        Merge terms from source block into target block.

        Args:
            source_block_id: ID of block to merge from
            target_block_id: ID of block to merge into
            delete_source: Whether to delete source after merge

        Returns:
            True if merged, False if either block not found
        """
        source = self.get_block(source_block_id)
        target = self.get_block(target_block_id)

        if not source or not target:
            return False

        # Merge terms
        for term in source.pico_element.primary_terms:
            if term not in target.pico_element.primary_terms:
                target.pico_element.primary_terms.append(term)

        for term in source.pico_element.synonyms:
            if term not in target.pico_element.synonyms:
                target.pico_element.synonyms.append(term)

        for term in source.pico_element.mesh_terms:
            if term not in target.pico_element.mesh_terms:
                target.pico_element.mesh_terms.append(term)

        # Merge notes
        if source.pico_element.notes:
            if target.pico_element.notes:
                target.pico_element.notes += f"\n{source.pico_element.notes}"
            else:
                target.pico_element.notes = source.pico_element.notes

        if delete_source:
            self.remove_block(source_block_id)

        return True

    def duplicate_block(self, block_id: str, new_name: Optional[str] = None) -> Optional[ConceptBlock]:
        """
        Duplicate a concept block.

        Args:
            block_id: ID of block to duplicate
            new_name: Optional new name for the duplicate

        Returns:
            New ConceptBlock or None if source not found
        """
        source = self.get_block(block_id)
        if not source:
            return None

        new_block = self.create_new_block(
            name=new_name or f"{source.name} (Copy)",
            element_type=source.pico_element.element_type,
            label=source.pico_element.label,
            primary_terms=source.pico_element.primary_terms.copy(),
            synonyms=source.pico_element.synonyms.copy(),
            mesh_terms=source.pico_element.mesh_terms.copy(),
            notes=source.pico_element.notes,
        )

        return new_block

    def to_dict(self) -> list[dict]:
        """Convert all concept blocks to dictionaries."""
        return [block.model_dump() for block in self.concept_blocks]

    @classmethod
    def from_dict(cls, data: list[dict]) -> "ConceptBuilder":
        """Create ConceptBuilder from list of dictionaries."""
        blocks = [ConceptBlock.model_validate(d) for d in data]
        return cls(concept_blocks=blocks)

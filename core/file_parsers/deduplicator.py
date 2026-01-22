"""Deduplication logic for parsed references."""

import re
from typing import Optional
from dataclasses import dataclass

from ..storage.models import ParsedReference, DeduplicationResult


@dataclass
class DuplicateMatch:
    """A duplicate match between two references."""
    reference: ParsedReference
    duplicate_of: ParsedReference
    reason: str  # "doi", "title_fuzzy", "title_author_year"
    score: float


class Deduplicator:
    """Deduplicate parsed references from multiple sources."""

    def __init__(
        self,
        doi_match: bool = True,
        fuzzy_title_match: bool = True,
        title_author_year_match: bool = True,
        fuzzy_threshold: float = 0.85,
    ):
        """
        Initialize deduplicator.

        Args:
            doi_match: Enable DOI-based matching
            fuzzy_title_match: Enable fuzzy title matching
            title_author_year_match: Enable title+author+year matching
            fuzzy_threshold: Threshold for fuzzy matching (0-1)
        """
        self.doi_match = doi_match
        self.fuzzy_title_match = fuzzy_title_match
        self.title_author_year_match = title_author_year_match
        self.fuzzy_threshold = fuzzy_threshold

        # Try to import rapidfuzz
        self._rapidfuzz_available = False
        try:
            from rapidfuzz import fuzz
            self._rapidfuzz_available = True
            self._fuzz = fuzz
        except ImportError:
            pass

    def deduplicate(
        self,
        references: list[ParsedReference],
        project_id: str = "",
    ) -> DeduplicationResult:
        """
        Deduplicate a list of references.

        Args:
            references: List of ParsedReference objects
            project_id: Project ID for the result

        Returns:
            DeduplicationResult with statistics and marked duplicates
        """
        if not references:
            return DeduplicationResult(
                project_id=project_id,
                total_records=0,
                unique_records=0,
                duplicate_count=0,
            )

        # Track duplicates
        duplicates = []  # List of DuplicateMatch

        # Index references by DOI and normalized title
        doi_index = {}
        title_index = {}

        for ref in references:
            # DOI indexing
            if ref.doi:
                normalized_doi = self._normalize_doi(ref.doi)
                if normalized_doi in doi_index:
                    duplicates.append(DuplicateMatch(
                        reference=ref,
                        duplicate_of=doi_index[normalized_doi],
                        reason="doi",
                        score=1.0,
                    ))
                else:
                    doi_index[normalized_doi] = ref

            # Title indexing for non-DOI matches
            normalized_title = self._normalize_title(ref.title)
            if normalized_title:
                if normalized_title not in title_index:
                    title_index[normalized_title] = []
                title_index[normalized_title].append(ref)

        # Find fuzzy title matches (for refs not already matched by DOI)
        matched_ids = {d.reference.id for d in duplicates}

        if self.fuzzy_title_match and self._rapidfuzz_available:
            duplicates.extend(self._find_fuzzy_matches(references, matched_ids))
            matched_ids = {d.reference.id for d in duplicates}

        # Find title+author+year matches
        if self.title_author_year_match:
            duplicates.extend(self._find_title_author_year_matches(references, matched_ids))

        # Mark duplicates on references
        duplicate_ids = {}
        for match in duplicates:
            duplicate_ids[match.reference.id] = match

        for ref in references:
            if ref.id in duplicate_ids:
                match = duplicate_ids[ref.id]
                ref.is_duplicate = True
                ref.duplicate_of = match.duplicate_of.id
                ref.duplicate_reason = match.reason
                ref.duplicate_score = match.score

        # Calculate statistics
        records_per_source = {}
        for ref in references:
            source = ref.source_database or "Unknown"
            records_per_source[source] = records_per_source.get(source, 0) + 1

        doi_duplicates = sum(1 for d in duplicates if d.reason == "doi")
        title_fuzzy_duplicates = sum(1 for d in duplicates if d.reason == "title_fuzzy")
        title_author_year_duplicates = sum(1 for d in duplicates if d.reason == "title_author_year")

        return DeduplicationResult(
            project_id=project_id,
            records_per_source=records_per_source,
            total_records=len(references),
            unique_records=len(references) - len(duplicates),
            duplicate_count=len(duplicates),
            doi_duplicates=doi_duplicates,
            title_fuzzy_duplicates=title_fuzzy_duplicates,
            title_author_year_duplicates=title_author_year_duplicates,
            all_references=references,
        )

    def _find_fuzzy_matches(
        self,
        references: list[ParsedReference],
        already_matched: set[str],
    ) -> list[DuplicateMatch]:
        """Find fuzzy title matches using rapidfuzz."""
        matches = []

        # Get unmatched references
        unmatched = [r for r in references if r.id not in already_matched]

        # Compare each pair
        for i, ref1 in enumerate(unmatched):
            if ref1.id in already_matched:
                continue

            title1 = self._normalize_title(ref1.title)
            if not title1:
                continue

            for ref2 in unmatched[i + 1:]:
                if ref2.id in already_matched:
                    continue

                title2 = self._normalize_title(ref2.title)
                if not title2:
                    continue

                # Calculate similarity
                score = self._fuzz.ratio(title1, title2) / 100.0

                if score >= self.fuzzy_threshold:
                    # Keep the one with more information
                    if self._count_fields(ref1) >= self._count_fields(ref2):
                        matches.append(DuplicateMatch(
                            reference=ref2,
                            duplicate_of=ref1,
                            reason="title_fuzzy",
                            score=score,
                        ))
                        already_matched.add(ref2.id)
                    else:
                        matches.append(DuplicateMatch(
                            reference=ref1,
                            duplicate_of=ref2,
                            reason="title_fuzzy",
                            score=score,
                        ))
                        already_matched.add(ref1.id)

        return matches

    def _find_title_author_year_matches(
        self,
        references: list[ParsedReference],
        already_matched: set[str],
    ) -> list[DuplicateMatch]:
        """Find matches based on title + first author + year."""
        matches = []

        # Build index by (normalized_title_start, year, first_author_lastname)
        index = {}

        for ref in references:
            if ref.id in already_matched:
                continue

            key = self._make_title_author_year_key(ref)
            if not key:
                continue

            if key in index:
                existing = index[key]
                if self._count_fields(existing) >= self._count_fields(ref):
                    matches.append(DuplicateMatch(
                        reference=ref,
                        duplicate_of=existing,
                        reason="title_author_year",
                        score=0.9,
                    ))
                    already_matched.add(ref.id)
                else:
                    matches.append(DuplicateMatch(
                        reference=existing,
                        duplicate_of=ref,
                        reason="title_author_year",
                        score=0.9,
                    ))
                    already_matched.add(existing.id)
                    index[key] = ref
            else:
                index[key] = ref

        return matches

    def _normalize_doi(self, doi: str) -> str:
        """Normalize a DOI for comparison."""
        doi = doi.strip().lower()

        # Remove common prefixes
        prefixes = [
            "https://doi.org/",
            "http://doi.org/",
            "https://dx.doi.org/",
            "http://dx.doi.org/",
            "doi:",
        ]
        for prefix in prefixes:
            if doi.startswith(prefix):
                doi = doi[len(prefix):]
                break

        return doi

    def _normalize_title(self, title: str) -> str:
        """Normalize a title for comparison."""
        if not title:
            return ""

        # Lowercase
        title = title.lower()

        # Remove punctuation
        title = re.sub(r'[^\w\s]', ' ', title)

        # Normalize whitespace
        title = ' '.join(title.split())

        return title

    def _make_title_author_year_key(self, ref: ParsedReference) -> Optional[str]:
        """Create a key for title+author+year matching."""
        title = self._normalize_title(ref.title)
        if not title:
            return None

        # Get first 50 chars of title
        title_start = title[:50]

        # Get year
        year = ref.year or 0

        # Get first author last name
        first_author = ""
        if ref.authors:
            # Take first author, get last name
            first = ref.authors.split(";")[0].strip()
            # Try to get last name
            parts = first.split(",")
            if parts:
                first_author = parts[0].strip().lower()

        return f"{title_start}|{year}|{first_author}"

    def _count_fields(self, ref: ParsedReference) -> int:
        """Count non-null fields in a reference (for choosing which to keep)."""
        count = 0
        if ref.title:
            count += 1
        if ref.abstract:
            count += 2  # Abstract is valuable
        if ref.authors:
            count += 1
        if ref.year:
            count += 1
        if ref.journal:
            count += 1
        if ref.doi:
            count += 2  # DOI is valuable
        if ref.pmid:
            count += 1
        return count

    def get_unique_references(
        self,
        result: DeduplicationResult,
    ) -> list[ParsedReference]:
        """Get only unique (non-duplicate) references from a result."""
        return [r for r in result.all_references if not r.is_duplicate]

    def get_duplicate_groups(
        self,
        result: DeduplicationResult,
    ) -> list[list[ParsedReference]]:
        """
        Get groups of duplicate references.

        Returns:
            List of groups, where each group is a list of duplicate references
        """
        # Build groups by duplicate_of ID
        groups = {}

        for ref in result.all_references:
            if ref.is_duplicate and ref.duplicate_of:
                if ref.duplicate_of not in groups:
                    groups[ref.duplicate_of] = []
                groups[ref.duplicate_of].append(ref)

        # Add the "master" reference to each group
        ref_by_id = {r.id: r for r in result.all_references}
        result_groups = []

        for master_id, duplicates in groups.items():
            group = [ref_by_id[master_id]] + duplicates
            result_groups.append(group)

        return result_groups

    def merge_duplicate_group(
        self,
        group: list[ParsedReference],
    ) -> ParsedReference:
        """
        Merge a group of duplicates into a single best reference.

        Args:
            group: List of duplicate references

        Returns:
            Merged reference with best available data
        """
        if not group:
            raise ValueError("Cannot merge empty group")

        if len(group) == 1:
            return group[0]

        # Sort by field count (descending) to get best reference
        sorted_group = sorted(group, key=self._count_fields, reverse=True)
        best = sorted_group[0]

        # Merge fields from others
        merged = ParsedReference(
            source_file=best.source_file,
            source_database=best.source_database,
            title=best.title,
            abstract=best.abstract,
            authors=best.authors,
            year=best.year,
            journal=best.journal,
            doi=best.doi,
            pmid=best.pmid,
        )

        # Fill in missing fields from other references
        for ref in sorted_group[1:]:
            if not merged.abstract and ref.abstract:
                merged.abstract = ref.abstract
            if not merged.authors and ref.authors:
                merged.authors = ref.authors
            if not merged.year and ref.year:
                merged.year = ref.year
            if not merged.journal and ref.journal:
                merged.journal = ref.journal
            if not merged.doi and ref.doi:
                merged.doi = ref.doi
            if not merged.pmid and ref.pmid:
                merged.pmid = ref.pmid

        return merged

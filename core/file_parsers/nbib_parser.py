"""NBIB (PubMed) file parser for reference management."""

import re
from typing import Optional

from ..storage.models import ParsedReference


class NBIBParser:
    """Parse NBIB (PubMed/MEDLINE) format files."""

    # NBIB tag mappings
    TAG_MAPPING = {
        "TI": "title",
        "AB": "abstract",
        "AU": "authors",
        "FAU": "authors_full",
        "DP": "date",
        "JT": "journal",
        "TA": "journal_abbrev",
        "AID": "identifiers",
        "PMID": "pmid",
        "PMC": "pmcid",
        "LID": "identifiers",
        "SO": "source",
    }

    def __init__(self, source_file: str = ""):
        """
        Initialize NBIB parser.

        Args:
            source_file: Name of the source file being parsed
        """
        self.source_file = source_file

    def parse(self, content: str) -> list[ParsedReference]:
        """
        Parse NBIB content into ParsedReference objects.

        Args:
            content: NBIB file content as string

        Returns:
            List of ParsedReference objects
        """
        references = []
        records = self._split_records(content)

        for record_text in records:
            record = self._parse_record(record_text)
            if record:
                ref = self._create_reference(record)
                if ref:
                    references.append(ref)

        return references

    def parse_file(self, filepath: str) -> list[ParsedReference]:
        """
        Parse an NBIB file.

        Args:
            filepath: Path to the NBIB file

        Returns:
            List of ParsedReference objects
        """
        self.source_file = filepath

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return self.parse(content)

    def _split_records(self, content: str) -> list[str]:
        """Split content into individual records."""
        # Records are separated by blank lines
        records = []
        current_record = []

        for line in content.split("\n"):
            if line.strip() == "" and current_record:
                # Check if this looks like a complete record
                record_text = "\n".join(current_record)
                if "PMID" in record_text or "TI" in record_text:
                    records.append(record_text)
                current_record = []
            else:
                current_record.append(line)

        # Handle last record
        if current_record:
            record_text = "\n".join(current_record)
            if "PMID" in record_text or "TI" in record_text:
                records.append(record_text)

        return records

    def _parse_record(self, record_text: str) -> dict:
        """Parse a single record into a dictionary."""
        record = {}
        current_tag = None
        current_value = []

        for line in record_text.split("\n"):
            # NBIB format: "TAG - value" with possible continuation lines
            tag_match = re.match(r'^([A-Z]+)\s*-\s*(.*)$', line)

            if tag_match:
                # Save previous tag/value
                if current_tag:
                    self._add_to_record(record, current_tag, " ".join(current_value))

                current_tag = tag_match.group(1)
                current_value = [tag_match.group(2).strip()]
            elif line.startswith("      ") and current_tag:
                # Continuation line (6 spaces)
                current_value.append(line.strip())
            elif line.strip() and current_tag:
                # Other continuation
                current_value.append(line.strip())

        # Save last tag/value
        if current_tag:
            self._add_to_record(record, current_tag, " ".join(current_value))

        return record

    def _add_to_record(self, record: dict, tag: str, value: str) -> None:
        """Add a tag/value pair to the record."""
        field = self.TAG_MAPPING.get(tag, tag.lower())

        if field in ["authors", "authors_full"]:
            # Accumulate authors
            if "authors" not in record:
                record["authors"] = []
            record["authors"].append(value)
        elif field == "identifiers":
            # Parse DOI and other identifiers
            if "identifiers" not in record:
                record["identifiers"] = []
            record["identifiers"].append(value)
        else:
            record[field] = value

    def _create_reference(self, record: dict) -> Optional[ParsedReference]:
        """Create a ParsedReference from a parsed record."""
        title = record.get("title", "").strip()
        if not title:
            return None

        # Process authors
        authors = None
        if "authors" in record:
            authors = "; ".join(record["authors"])

        # Parse year from date
        year = self._parse_year(record.get("date", ""))

        # Extract DOI from identifiers
        doi = self._extract_doi(record.get("identifiers", []))

        # Get journal
        journal = record.get("journal") or record.get("journal_abbrev")

        # Get PMID
        pmid = record.get("pmid", "")
        if pmid:
            pmid = re.sub(r'\D', '', pmid)  # Keep only digits

        return ParsedReference(
            source_file=self.source_file,
            source_database="PubMed",
            title=title,
            abstract=record.get("abstract") or None,
            authors=authors,
            year=year,
            journal=journal,
            doi=doi,
            pmid=pmid or None,
        )

    def _parse_year(self, date_str: str) -> Optional[int]:
        """Parse year from NBIB date format."""
        if not date_str:
            return None

        # NBIB date format is typically "YYYY Mon DD" or "YYYY"
        match = re.search(r'(19|20)\d{2}', date_str)
        if match:
            return int(match.group(0))

        return None

    def _extract_doi(self, identifiers: list[str]) -> Optional[str]:
        """Extract and normalize DOI from identifiers."""
        for identifier in identifiers:
            # Look for DOI pattern
            if "[doi]" in identifier.lower():
                doi = re.sub(r'\s*\[doi\]\s*', '', identifier, flags=re.IGNORECASE)
                return self._normalize_doi(doi)

            # Check if it looks like a DOI
            if identifier.startswith("10."):
                return self._normalize_doi(identifier)

        return None

    def _normalize_doi(self, doi: str) -> str:
        """Normalize a DOI string."""
        doi = doi.strip()

        # Remove common prefixes
        prefixes = [
            "https://doi.org/",
            "http://doi.org/",
            "https://dx.doi.org/",
            "http://dx.doi.org/",
            "doi:",
            "DOI:",
        ]
        for prefix in prefixes:
            if doi.startswith(prefix):
                doi = doi[len(prefix):]
                break

        return doi.strip().lower()

    @staticmethod
    def is_nbib_format(content: str) -> bool:
        """
        Check if content appears to be in NBIB format.

        Args:
            content: File content to check

        Returns:
            True if likely NBIB format
        """
        # Look for characteristic NBIB tags
        nbib_tags = ["PMID-", "TI  -", "AB  -", "AU  -", "DP  -"]
        for tag in nbib_tags:
            if tag in content:
                return True
        return False

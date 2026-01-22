"""RIS file parser for reference management."""

import re
from typing import Optional
from io import StringIO

from ..storage.models import ParsedReference


class RISParser:
    """Parse RIS (Research Information Systems) format files."""

    # RIS tag mappings
    TAG_MAPPING = {
        "TI": "title",
        "T1": "title",
        "AB": "abstract",
        "N2": "abstract",
        "AU": "authors",
        "A1": "authors",
        "PY": "year",
        "Y1": "year",
        "DA": "year",
        "JO": "journal",
        "JF": "journal",
        "JA": "journal",
        "T2": "journal",
        "DO": "doi",
        "AN": "pmid",
        "DB": "source_database",
        "DP": "source_database",
    }

    # Database name normalization
    DATABASE_NAMES = {
        "pubmed": "PubMed",
        "medline": "PubMed",
        "embase": "EMBASE",
        "scopus": "SCOPUS",
        "web of science": "WOS",
        "wos": "WOS",
        "cochrane": "Cochrane",
        "psycinfo": "PsycINFO",
        "cinahl": "CINAHL",
    }

    def __init__(self, source_file: str = "", default_database: str = "Unknown"):
        """
        Initialize RIS parser.

        Args:
            source_file: Name of the source file being parsed
            default_database: Default database name if not specified in file
        """
        self.source_file = source_file
        self.default_database = default_database

    def parse(self, content: str) -> list[ParsedReference]:
        """
        Parse RIS content into ParsedReference objects.

        Args:
            content: RIS file content as string

        Returns:
            List of ParsedReference objects
        """
        references = []
        current_record = {}
        current_tag = None

        for line in content.split("\n"):
            line = line.rstrip()

            # Check for tag line (format: "TI  - Title text")
            tag_match = re.match(r'^([A-Z][A-Z0-9])\s{1,2}-\s*(.*)$', line)

            if tag_match:
                tag = tag_match.group(1)
                value = tag_match.group(2).strip()

                if tag == "ER":
                    # End of record
                    if current_record:
                        ref = self._create_reference(current_record)
                        if ref:
                            references.append(ref)
                    current_record = {}
                    current_tag = None
                elif tag == "TY":
                    # Type of reference (start of new record)
                    current_record = {"type": value}
                    current_tag = None
                else:
                    current_tag = tag
                    field = self.TAG_MAPPING.get(tag)
                    if field:
                        if field in current_record:
                            # Append for multi-value fields (like authors)
                            if field == "authors":
                                current_record[field] = f"{current_record[field]}; {value}"
                            else:
                                current_record[field] += f" {value}"
                        else:
                            current_record[field] = value

            elif line.strip() and current_tag:
                # Continuation line
                field = self.TAG_MAPPING.get(current_tag)
                if field and field in current_record:
                    current_record[field] += f" {line.strip()}"

        # Handle last record if no ER tag
        if current_record:
            ref = self._create_reference(current_record)
            if ref:
                references.append(ref)

        return references

    def parse_file(self, filepath: str) -> list[ParsedReference]:
        """
        Parse an RIS file.

        Args:
            filepath: Path to the RIS file

        Returns:
            List of ParsedReference objects
        """
        self.source_file = filepath

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return self.parse(content)

    def _create_reference(self, record: dict) -> Optional[ParsedReference]:
        """Create a ParsedReference from a parsed record."""
        title = record.get("title", "").strip()
        if not title:
            return None

        # Clean and normalize DOI
        doi = record.get("doi", "")
        if doi:
            doi = self._normalize_doi(doi)

        # Clean and normalize PMID
        pmid = record.get("pmid", "")
        if pmid:
            pmid = self._normalize_pmid(pmid)

        # Parse year
        year = self._parse_year(record.get("year", ""))

        # Normalize database name
        source_db = record.get("source_database", self.default_database)
        source_db = self._normalize_database(source_db)

        return ParsedReference(
            source_file=self.source_file,
            source_database=source_db,
            title=title,
            abstract=record.get("abstract", "").strip() or None,
            authors=record.get("authors", "").strip() or None,
            year=year,
            journal=record.get("journal", "").strip() or None,
            doi=doi or None,
            pmid=pmid or None,
        )

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

    def _normalize_pmid(self, pmid: str) -> str:
        """Normalize a PMID string."""
        pmid = pmid.strip()

        # Extract numeric PMID
        match = re.search(r'(\d+)', pmid)
        if match:
            return match.group(1)

        return pmid

    def _parse_year(self, year_str: str) -> Optional[int]:
        """Parse year from various formats."""
        if not year_str:
            return None

        # Try to find a 4-digit year
        match = re.search(r'(19|20)\d{2}', year_str)
        if match:
            return int(match.group(0))

        return None

    def _normalize_database(self, db_name: str) -> str:
        """Normalize database name."""
        if not db_name:
            return self.default_database

        db_lower = db_name.lower().strip()
        for key, normalized in self.DATABASE_NAMES.items():
            if key in db_lower:
                return normalized

        return db_name

    @staticmethod
    def detect_database_from_content(content: str) -> str:
        """
        Try to detect the source database from RIS content.

        Args:
            content: RIS file content

        Returns:
            Detected database name or "Unknown"
        """
        content_lower = content.lower()

        if "pubmed" in content_lower or "medline" in content_lower:
            return "PubMed"
        elif "embase" in content_lower:
            return "EMBASE"
        elif "scopus" in content_lower:
            return "SCOPUS"
        elif "web of science" in content_lower or "wos" in content_lower:
            return "WOS"
        elif "cochrane" in content_lower:
            return "Cochrane"
        elif "psycinfo" in content_lower:
            return "PsycINFO"
        elif "cinahl" in content_lower:
            return "CINAHL"

        return "Unknown"

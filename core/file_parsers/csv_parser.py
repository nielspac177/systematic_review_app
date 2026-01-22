"""CSV file parser for reference management with auto-detection."""

import re
from typing import Optional
from io import StringIO
import csv

from ..storage.models import ParsedReference


class CSVReferenceParser:
    """Parse CSV files with automatic column detection."""

    # Column name patterns for auto-detection (lowercase)
    TITLE_PATTERNS = [
        "title", "article_title", "article title", "ti", "document title",
        "paper title", "study title", "record title", "document_title",
    ]

    ABSTRACT_PATTERNS = [
        "abstract", "ab", "summary", "description", "abstract text",
        "article_abstract", "article abstract", "content",
    ]

    AUTHOR_PATTERNS = [
        "author", "authors", "au", "author(s)", "article author",
        "first author", "article_author", "creator", "creators",
    ]

    YEAR_PATTERNS = [
        "year", "publication year", "pub year", "date", "publication date",
        "py", "pub_year", "pubyear", "year published",
    ]

    JOURNAL_PATTERNS = [
        "journal", "source", "publication", "journal title", "source title",
        "periodical", "journal_title", "publication_name", "venue",
    ]

    DOI_PATTERNS = [
        "doi", "digital object identifier", "article doi", "doi number",
    ]

    PMID_PATTERNS = [
        "pmid", "pubmed id", "pubmed_id", "pubmed", "medline id",
        "accession number", "pubmed identifier",
    ]

    DATABASE_PATTERNS = [
        "database", "source database", "db", "source_database",
        "data source", "provider",
    ]

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
        "google scholar": "Google Scholar",
    }

    def __init__(self, source_file: str = "", default_database: str = "CSV"):
        """
        Initialize CSV parser.

        Args:
            source_file: Name of the source file being parsed
            default_database: Default database name if not specified
        """
        self.source_file = source_file
        self.default_database = default_database
        self._column_mapping = {}

    def parse(self, content: str) -> list[ParsedReference]:
        """
        Parse CSV content into ParsedReference objects.

        Args:
            content: CSV file content as string

        Returns:
            List of ParsedReference objects
        """
        references = []

        try:
            # Try to detect delimiter
            dialect = csv.Sniffer().sniff(content[:5000], delimiters=',;\t|')
        except csv.Error:
            dialect = csv.excel  # Default to comma-separated

        reader = csv.DictReader(StringIO(content), dialect=dialect)

        if not reader.fieldnames:
            return references

        # Auto-detect column mappings
        self._column_mapping = self.detect_columns(reader.fieldnames)

        if not self._column_mapping.get("title"):
            # No title column found, cannot parse
            return references

        for row in reader:
            ref = self._parse_row(row)
            if ref:
                references.append(ref)

        return references

    def parse_file(self, filepath: str) -> list[ParsedReference]:
        """
        Parse a CSV file.

        Args:
            filepath: Path to the CSV file

        Returns:
            List of ParsedReference objects
        """
        self.source_file = filepath

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return self.parse(content)

    def detect_columns(self, columns: list[str]) -> dict[str, Optional[str]]:
        """
        Auto-detect column mappings from column names.

        Args:
            columns: List of column names from CSV

        Returns:
            Dictionary mapping field names to detected column names
        """
        mapping = {
            "title": None,
            "abstract": None,
            "authors": None,
            "year": None,
            "journal": None,
            "doi": None,
            "pmid": None,
            "database": None,
        }

        columns_lower = {col.lower().strip(): col for col in columns}

        # Try to match each field
        mapping["title"] = self._find_matching_column(columns_lower, self.TITLE_PATTERNS)
        mapping["abstract"] = self._find_matching_column(columns_lower, self.ABSTRACT_PATTERNS)
        mapping["authors"] = self._find_matching_column(columns_lower, self.AUTHOR_PATTERNS)
        mapping["year"] = self._find_matching_column(columns_lower, self.YEAR_PATTERNS)
        mapping["journal"] = self._find_matching_column(columns_lower, self.JOURNAL_PATTERNS)
        mapping["doi"] = self._find_matching_column(columns_lower, self.DOI_PATTERNS)
        mapping["pmid"] = self._find_matching_column(columns_lower, self.PMID_PATTERNS)
        mapping["database"] = self._find_matching_column(columns_lower, self.DATABASE_PATTERNS)

        return mapping

    def _find_matching_column(
        self,
        columns_lower: dict[str, str],
        patterns: list[str],
    ) -> Optional[str]:
        """Find a column matching any of the given patterns."""
        # Exact match first
        for pattern in patterns:
            if pattern in columns_lower:
                return columns_lower[pattern]

        # Partial match (column contains pattern)
        for col_lower, col_original in columns_lower.items():
            for pattern in patterns:
                if pattern in col_lower or col_lower in pattern:
                    return col_original

        return None

    def _parse_row(self, row: dict) -> Optional[ParsedReference]:
        """Parse a single CSV row into a ParsedReference."""
        # Get title
        title_col = self._column_mapping.get("title")
        if not title_col or not row.get(title_col):
            return None

        title = str(row[title_col]).strip()
        if not title:
            return None

        # Get abstract
        abstract = None
        abstract_col = self._column_mapping.get("abstract")
        if abstract_col and row.get(abstract_col):
            abstract = str(row[abstract_col]).strip() or None

        # Get authors
        authors = None
        authors_col = self._column_mapping.get("authors")
        if authors_col and row.get(authors_col):
            authors = str(row[authors_col]).strip() or None

        # Get year
        year = None
        year_col = self._column_mapping.get("year")
        if year_col and row.get(year_col):
            year = self._parse_year(str(row[year_col]))

        # Get journal
        journal = None
        journal_col = self._column_mapping.get("journal")
        if journal_col and row.get(journal_col):
            journal = str(row[journal_col]).strip() or None

        # Get DOI
        doi = None
        doi_col = self._column_mapping.get("doi")
        if doi_col and row.get(doi_col):
            doi = self._normalize_doi(str(row[doi_col])) or None

        # Get PMID
        pmid = None
        pmid_col = self._column_mapping.get("pmid")
        if pmid_col and row.get(pmid_col):
            pmid = self._normalize_pmid(str(row[pmid_col])) or None

        # Get database
        source_db = self.default_database
        db_col = self._column_mapping.get("database")
        if db_col and row.get(db_col):
            source_db = self._normalize_database(str(row[db_col]))

        return ParsedReference(
            source_file=self.source_file,
            source_database=source_db,
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            journal=journal,
            doi=doi,
            pmid=pmid,
        )

    def _parse_year(self, year_str: str) -> Optional[int]:
        """Parse year from various formats."""
        if not year_str:
            return None

        # Try to find a 4-digit year
        match = re.search(r'(19|20)\d{2}', year_str)
        if match:
            return int(match.group(0))

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

    def _normalize_pmid(self, pmid: str) -> str:
        """Normalize a PMID string."""
        pmid = pmid.strip()

        # Extract numeric PMID
        match = re.search(r'(\d+)', pmid)
        if match:
            return match.group(1)

        return pmid

    def _normalize_database(self, db_name: str) -> str:
        """Normalize database name."""
        if not db_name:
            return self.default_database

        db_lower = db_name.lower().strip()
        for key, normalized in self.DATABASE_NAMES.items():
            if key in db_lower:
                return normalized

        return db_name

    def get_column_mapping(self) -> dict[str, Optional[str]]:
        """Get the detected column mapping (after parsing)."""
        return self._column_mapping.copy()

    @staticmethod
    def is_csv_format(content: str) -> bool:
        """
        Check if content appears to be CSV format.

        Args:
            content: File content to check

        Returns:
            True if likely CSV format
        """
        # Check first few lines for CSV structure
        lines = content.strip().split('\n')[:5]

        if not lines:
            return False

        # Try to detect delimiter
        try:
            dialect = csv.Sniffer().sniff('\n'.join(lines), delimiters=',;\t|')
            # Try to read as CSV
            reader = csv.reader(StringIO('\n'.join(lines)), dialect=dialect)
            rows = list(reader)
            # Should have consistent column count
            if len(rows) >= 2:
                col_count = len(rows[0])
                return all(len(row) == col_count for row in rows[:5] if row)
        except csv.Error:
            pass

        # Fallback: check for comma-separated structure
        if ',' in lines[0] or '\t' in lines[0] or ';' in lines[0]:
            return True

        return False

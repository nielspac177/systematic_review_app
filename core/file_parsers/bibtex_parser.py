"""BibTeX file parser for reference management."""

import re
from typing import Optional

from ..storage.models import ParsedReference


class BibTeXParser:
    """Parse BibTeX format files (.bib) from reference managers."""

    # Entry type mappings for study design hints
    ENTRY_TYPES = {
        "article": "Journal Article",
        "inproceedings": "Conference Paper",
        "proceedings": "Conference Proceedings",
        "book": "Book",
        "incollection": "Book Chapter",
        "inbook": "Book Chapter",
        "phdthesis": "Thesis",
        "mastersthesis": "Thesis",
        "techreport": "Technical Report",
        "misc": "Miscellaneous",
        "unpublished": "Unpublished",
    }

    # Database detection from common BibTeX sources
    DATABASE_HINTS = {
        "google scholar": "Google Scholar",
        "scholar.google": "Google Scholar",
        "pubmed": "PubMed",
        "scopus": "SCOPUS",
        "web of science": "WOS",
        "ieee": "IEEE",
        "acm": "ACM",
        "springer": "Springer",
        "elsevier": "Elsevier",
        "wiley": "Wiley",
    }

    def __init__(self, source_file: str = "", default_database: str = "BibTeX"):
        """
        Initialize BibTeX parser.

        Args:
            source_file: Name of the source file being parsed
            default_database: Default database name if not detected
        """
        self.source_file = source_file
        self.default_database = default_database

    def parse(self, content: str) -> list[ParsedReference]:
        """
        Parse BibTeX content into ParsedReference objects.

        Args:
            content: BibTeX file content as string

        Returns:
            List of ParsedReference objects
        """
        references = []
        entries = self._extract_entries(content)

        for entry in entries:
            ref = self._parse_entry(entry)
            if ref:
                references.append(ref)

        return references

    def parse_file(self, filepath: str) -> list[ParsedReference]:
        """
        Parse a BibTeX file.

        Args:
            filepath: Path to the BibTeX file

        Returns:
            List of ParsedReference objects
        """
        self.source_file = filepath

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return self.parse(content)

    def _extract_entries(self, content: str) -> list[str]:
        """
        Extract individual BibTeX entries from content.

        BibTeX entries have the format:
        @type{key,
            field = {value},
            ...
        }
        """
        entries = []

        # Find all entry starts: @type{key,
        entry_pattern = re.compile(r'@(\w+)\s*\{([^,]*),', re.IGNORECASE)

        # Track brace depth to find entry boundaries
        pos = 0
        while pos < len(content):
            match = entry_pattern.search(content, pos)
            if not match:
                break

            start = match.start()
            # Find the opening brace
            brace_start = content.find('{', start)
            if brace_start == -1:
                pos = start + 1
                continue

            # Find matching closing brace
            depth = 1
            i = brace_start + 1
            while i < len(content) and depth > 0:
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                i += 1

            if depth == 0:
                entry = content[start:i]
                entries.append(entry)
                pos = i
            else:
                pos = start + 1

        return entries

    def _parse_entry(self, entry: str) -> Optional[ParsedReference]:
        """Parse a single BibTeX entry into a ParsedReference."""
        # Extract entry type and key
        header_match = re.match(r'@(\w+)\s*\{([^,]*),', entry, re.IGNORECASE)
        if not header_match:
            return None

        entry_type = header_match.group(1).lower()

        # Skip comments and preambles
        if entry_type in ["comment", "preamble", "string"]:
            return None

        # Parse fields
        fields = self._parse_fields(entry)

        # Extract title
        title = self._get_field(fields, ["title"])
        if not title:
            return None

        # Extract other fields
        abstract = self._get_field(fields, ["abstract", "summary"])
        authors = self._parse_authors(self._get_field(fields, ["author", "authors"]))
        year = self._parse_year(self._get_field(fields, ["year", "date"]))
        journal = self._get_field(fields, ["journal", "journaltitle", "booktitle", "publisher"])
        doi = self._normalize_doi(self._get_field(fields, ["doi"]))

        # Try to extract PMID from various fields
        pmid = self._extract_pmid(fields)

        # Detect source database
        source_db = self._detect_database(fields, entry)

        return ParsedReference(
            source_file=self.source_file,
            source_database=source_db,
            title=title,
            abstract=abstract or None,
            authors=authors or None,
            year=year,
            journal=journal or None,
            doi=doi or None,
            pmid=pmid or None,
        )

    def _parse_fields(self, entry: str) -> dict[str, str]:
        """Parse BibTeX fields from an entry."""
        fields = {}

        # Remove the header line
        entry_body = re.sub(r'^@\w+\s*\{[^,]*,\s*', '', entry, flags=re.IGNORECASE)
        # Remove trailing brace
        entry_body = re.sub(r'\}\s*$', '', entry_body)

        # Parse field = value pairs
        # Handles both {braced} and "quoted" values
        field_pattern = re.compile(
            r'(\w+)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|"([^"]*)"|(\d+))',
            re.IGNORECASE | re.DOTALL
        )

        for match in field_pattern.finditer(entry_body):
            field_name = match.group(1).lower()
            # Get value from braces, quotes, or number
            value = match.group(2) or match.group(3) or match.group(4) or ""
            # Clean up the value
            value = self._clean_value(value)
            if value:
                fields[field_name] = value

        return fields

    def _clean_value(self, value: str) -> str:
        """Clean a BibTeX field value."""
        if not value:
            return ""

        # Remove nested braces used for capitalization preservation
        value = re.sub(r'\{([^{}]*)\}', r'\1', value)

        # Remove LaTeX commands
        value = re.sub(r'\\[a-zA-Z]+\s*', '', value)

        # Remove special characters
        value = value.replace('~', ' ')
        value = value.replace('\\&', '&')
        value = value.replace('\\%', '%')

        # Normalize whitespace
        value = ' '.join(value.split())

        return value.strip()

    def _get_field(self, fields: dict[str, str], names: list[str]) -> str:
        """Get a field value by trying multiple possible names."""
        for name in names:
            if name in fields:
                return fields[name]
        return ""

    def _parse_authors(self, authors_str: str) -> str:
        """Parse BibTeX author format to semicolon-separated list."""
        if not authors_str:
            return ""

        # BibTeX uses "and" to separate authors
        authors = re.split(r'\s+and\s+', authors_str, flags=re.IGNORECASE)

        # Clean up each author
        cleaned = []
        for author in authors:
            author = author.strip()
            if author:
                # Convert "Last, First" or "First Last" to consistent format
                cleaned.append(author)

        return "; ".join(cleaned)

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
        if not doi:
            return ""

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

    def _extract_pmid(self, fields: dict[str, str]) -> str:
        """Try to extract PMID from various fields."""
        # Check direct PMID field
        pmid = fields.get("pmid", "")
        if pmid:
            match = re.search(r'(\d+)', pmid)
            if match:
                return match.group(1)

        # Check eprint field (sometimes used for PMID)
        eprint = fields.get("eprint", "")
        if "pubmed" in fields.get("eprinttype", "").lower():
            match = re.search(r'(\d+)', eprint)
            if match:
                return match.group(1)

        # Check URL for pubmed
        url = fields.get("url", "")
        if "pubmed" in url.lower() or "ncbi.nlm.nih.gov" in url.lower():
            match = re.search(r'/(\d+)', url)
            if match:
                return match.group(1)

        return ""

    def _detect_database(self, fields: dict[str, str], entry: str) -> str:
        """Detect source database from entry content."""
        # Check for explicit database field
        db = fields.get("database", "") or fields.get("source", "")
        if db:
            db_lower = db.lower()
            for hint, name in self.DATABASE_HINTS.items():
                if hint in db_lower:
                    return name

        # Check URL
        url = fields.get("url", "").lower()
        for hint, name in self.DATABASE_HINTS.items():
            if hint in url:
                return name

        # Check if this looks like a PubMed entry
        if fields.get("pmid") or "pubmed" in entry.lower():
            return "PubMed"

        return self.default_database

    @staticmethod
    def is_bibtex_format(content: str) -> bool:
        """
        Check if content appears to be in BibTeX format.

        Args:
            content: File content to check

        Returns:
            True if likely BibTeX format
        """
        # Look for characteristic BibTeX entry patterns
        bibtex_patterns = [
            r'@article\s*\{',
            r'@book\s*\{',
            r'@inproceedings\s*\{',
            r'@incollection\s*\{',
            r'@misc\s*\{',
            r'@techreport\s*\{',
            r'@phdthesis\s*\{',
            r'@mastersthesis\s*\{',
        ]

        content_lower = content.lower()
        for pattern in bibtex_patterns:
            if re.search(pattern, content_lower):
                return True

        return False

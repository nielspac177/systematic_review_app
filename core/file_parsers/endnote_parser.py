"""EndNote XML file parser for reference management."""

import re
from typing import Optional
import xml.etree.ElementTree as ET

from ..storage.models import ParsedReference


class EndNoteXMLParser:
    """Parse EndNote XML format files from EndNote desktop and web."""

    def __init__(self, source_file: str = ""):
        """
        Initialize EndNote XML parser.

        Args:
            source_file: Name of the source file being parsed
        """
        self.source_file = source_file

    def parse(self, content: str) -> list[ParsedReference]:
        """
        Parse EndNote XML content into ParsedReference objects.

        Args:
            content: EndNote XML file content as string

        Returns:
            List of ParsedReference objects
        """
        references = []

        try:
            # Parse XML
            root = ET.fromstring(content)

            # EndNote XML can have records in different structures
            # Try to find record elements
            records = (
                root.findall(".//record") or
                root.findall(".//Record") or
                root.findall(".//RECORD") or
                root.findall(".//{*}record")  # namespace-agnostic
            )

            # If no records found, try alternative structures
            if not records:
                records = root.findall(".//rec") or root.findall(".//Rec")

            for record in records:
                ref = self._parse_record(record)
                if ref:
                    references.append(ref)

        except ET.ParseError as e:
            # Log error but return what we have
            pass

        return references

    def parse_file(self, filepath: str) -> list[ParsedReference]:
        """
        Parse an EndNote XML file.

        Args:
            filepath: Path to the EndNote XML file

        Returns:
            List of ParsedReference objects
        """
        self.source_file = filepath

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return self.parse(content)

    def _parse_record(self, record: ET.Element) -> Optional[ParsedReference]:
        """Parse a single EndNote XML record into a ParsedReference."""
        # Extract title - try multiple possible paths
        title = self._get_text(record, [
            ".//title",
            ".//titles/title",
            ".//primary-title",
            ".//Title",
            ".//TITLE",
        ])

        if not title:
            return None

        # Extract abstract
        abstract = self._get_text(record, [
            ".//abstract",
            ".//Abstract",
            ".//ABSTRACT",
        ])

        # Extract authors
        authors = self._parse_authors(record)

        # Extract year
        year = self._parse_year(record)

        # Extract journal
        journal = self._get_text(record, [
            ".//periodical/full-title",
            ".//secondary-title",
            ".//journal",
            ".//Journal",
            ".//full-title",
            ".//source-app",
        ])

        # Extract DOI
        doi = self._extract_doi(record)

        # Extract PMID
        pmid = self._extract_pmid(record)

        # Detect source database
        source_db = self._detect_database(record)

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

    def _get_text(self, element: ET.Element, paths: list[str]) -> str:
        """Get text from first matching path."""
        for path in paths:
            # Try case-insensitive search
            found = element.find(path)
            if found is not None and found.text:
                return found.text.strip()

            # Try lowercase path
            found = element.find(path.lower())
            if found is not None and found.text:
                return found.text.strip()

        return ""

    def _parse_authors(self, record: ET.Element) -> str:
        """Parse authors from various EndNote XML structures."""
        authors = []

        # Try different author paths
        author_paths = [
            ".//contributors/authors/author",
            ".//authors/author",
            ".//author",
            ".//Contributors/Authors/Author",
            ".//AUTHORS/AUTHOR",
        ]

        for path in author_paths:
            author_elements = record.findall(path)
            if author_elements:
                for auth in author_elements:
                    # Author might be simple text or have name components
                    if auth.text:
                        authors.append(auth.text.strip())
                    else:
                        # Try to get name components
                        name_parts = []

                        last_name = auth.find(".//last-name") or auth.find(".//Last-Name")
                        if last_name is not None and last_name.text:
                            name_parts.append(last_name.text.strip())

                        first_name = auth.find(".//first-name") or auth.find(".//First-Name")
                        if first_name is not None and first_name.text:
                            name_parts.append(first_name.text.strip())

                        if name_parts:
                            authors.append(", ".join(name_parts))

                if authors:
                    break

        return "; ".join(authors) if authors else ""

    def _parse_year(self, record: ET.Element) -> Optional[int]:
        """Parse year from EndNote XML record."""
        # Try various year paths
        year_paths = [
            ".//dates/year",
            ".//year",
            ".//pub-dates/date",
            ".//Year",
            ".//YEAR",
        ]

        for path in year_paths:
            elem = record.find(path)
            if elem is not None and elem.text:
                match = re.search(r'(19|20)\d{2}', elem.text)
                if match:
                    return int(match.group(0))

        return None

    def _extract_doi(self, record: ET.Element) -> Optional[str]:
        """Extract DOI from EndNote XML record."""
        # Try electronic-resource-num (common in EndNote)
        doi_paths = [
            ".//electronic-resource-num",
            ".//doi",
            ".//DOI",
            ".//urls/related-urls/url",  # Sometimes DOI is stored as URL
        ]

        for path in doi_paths:
            elem = record.find(path)
            if elem is not None and elem.text:
                doi = elem.text.strip()
                # Check if this looks like a DOI
                if doi.startswith("10.") or "doi.org" in doi:
                    return self._normalize_doi(doi)

        # Check custom fields
        for custom in record.findall(".//custom*"):
            if custom.text and ("10." in custom.text or "doi" in custom.text.lower()):
                doi = custom.text.strip()
                if doi.startswith("10.") or "doi.org" in doi:
                    return self._normalize_doi(doi)

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

    def _extract_pmid(self, record: ET.Element) -> Optional[str]:
        """Extract PMID from EndNote XML record."""
        # Try accession-num (often contains PMID for PubMed records)
        pmid_paths = [
            ".//accession-num",
            ".//pmid",
            ".//PMID",
            ".//database-provider/accession-number",
        ]

        for path in pmid_paths:
            elem = record.find(path)
            if elem is not None and elem.text:
                # Extract numeric PMID
                match = re.search(r'(\d{7,9})', elem.text)
                if match:
                    return match.group(1)

        # Check remote-database-provider for PubMed indicator
        remote_db = record.find(".//remote-database-name")
        if remote_db is not None and remote_db.text:
            if "pubmed" in remote_db.text.lower() or "medline" in remote_db.text.lower():
                # Look for accession number
                accession = record.find(".//accession-num")
                if accession is not None and accession.text:
                    match = re.search(r'(\d+)', accession.text)
                    if match:
                        return match.group(1)

        return None

    def _detect_database(self, record: ET.Element) -> str:
        """Detect source database from record metadata."""
        # Check explicit database fields
        db_paths = [
            ".//remote-database-name",
            ".//database",
            ".//source-app",
        ]

        for path in db_paths:
            elem = record.find(path)
            if elem is not None and elem.text:
                db_name = elem.text.lower()
                if "pubmed" in db_name or "medline" in db_name:
                    return "PubMed"
                elif "embase" in db_name:
                    return "EMBASE"
                elif "scopus" in db_name:
                    return "SCOPUS"
                elif "web of science" in db_name or "wos" in db_name:
                    return "WOS"
                elif "cochrane" in db_name:
                    return "Cochrane"
                elif "psycinfo" in db_name:
                    return "PsycINFO"
                elif "cinahl" in db_name:
                    return "CINAHL"

        # Check for PMID as indicator of PubMed source
        if self._extract_pmid(record):
            return "PubMed"

        return "EndNote"

    @staticmethod
    def is_endnote_xml(content: str) -> bool:
        """
        Check if content appears to be in EndNote XML format.

        Args:
            content: File content to check

        Returns:
            True if likely EndNote XML format
        """
        # Check for XML declaration and EndNote-specific elements
        content_lower = content.lower()

        # Must be XML
        if not (content.strip().startswith("<?xml") or content.strip().startswith("<")):
            return False

        # Look for EndNote-specific markers
        endnote_markers = [
            "<xml><records>",
            "<records>",
            "<endnote",
            "endnote.dtd",
            "<record>",
            "<ref-type",
            "<contributors>",
            "<periodical>",
            "<electronic-resource-num>",
            "source-app=\"endnote\"",
        ]

        for marker in endnote_markers:
            if marker in content_lower:
                return True

        return False

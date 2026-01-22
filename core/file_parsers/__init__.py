"""File parsing module for reference files (RIS, NBIB, BibTeX, EndNote XML, CSV)."""

from .ris_parser import RISParser
from .nbib_parser import NBIBParser
from .bibtex_parser import BibTeXParser
from .endnote_parser import EndNoteXMLParser
from .csv_parser import CSVReferenceParser
from .deduplicator import Deduplicator

__all__ = [
    "RISParser",
    "NBIBParser",
    "BibTeXParser",
    "EndNoteXMLParser",
    "CSVReferenceParser",
    "Deduplicator",
]

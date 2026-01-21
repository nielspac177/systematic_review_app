"""PDF text extraction with dual methods (direct + OCR)."""

import os
import tempfile
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from pdf2image import convert_from_path
    import pytesseract
except ImportError:
    convert_from_path = None
    pytesseract = None


@dataclass
class ExtractionResult:
    """Result of PDF text extraction."""
    text: str
    method: str  # "direct", "ocr", or "combined"
    word_count: int
    page_count: int
    success: bool
    error: Optional[str] = None


class PDFProcessor:
    """Extract text from PDFs using direct extraction and OCR."""

    def __init__(
        self,
        ocr_enabled: bool = True,
        tesseract_cmd: Optional[str] = None,
        dpi: int = 200,
    ):
        """
        Initialize PDF processor.

        Args:
            ocr_enabled: Whether to enable OCR fallback
            tesseract_cmd: Path to tesseract executable (if not in PATH)
            dpi: DPI for PDF to image conversion (higher = better OCR, slower)
        """
        self.ocr_enabled = ocr_enabled
        self.dpi = dpi

        if tesseract_cmd and pytesseract:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def _extract_direct(self, pdf_path: str) -> ExtractionResult:
        """
        Extract text directly from PDF using PyPDF2.

        Args:
            pdf_path: Path to PDF file

        Returns:
            ExtractionResult with extracted text
        """
        if PyPDF2 is None:
            return ExtractionResult(
                text="",
                method="direct",
                word_count=0,
                page_count=0,
                success=False,
                error="PyPDF2 not installed",
            )

        try:
            text_parts = []
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                page_count = len(reader.pages)

                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            text = "\n\n".join(text_parts)
            word_count = len(text.split())

            return ExtractionResult(
                text=text,
                method="direct",
                word_count=word_count,
                page_count=page_count,
                success=True,
            )

        except Exception as e:
            return ExtractionResult(
                text="",
                method="direct",
                word_count=0,
                page_count=0,
                success=False,
                error=str(e),
            )

    def _extract_ocr(self, pdf_path: str) -> ExtractionResult:
        """
        Extract text from PDF using OCR.

        Args:
            pdf_path: Path to PDF file

        Returns:
            ExtractionResult with extracted text
        """
        if convert_from_path is None or pytesseract is None:
            return ExtractionResult(
                text="",
                method="ocr",
                word_count=0,
                page_count=0,
                success=False,
                error="pdf2image or pytesseract not installed",
            )

        try:
            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=self.dpi)
            page_count = len(images)

            text_parts = []
            for image in images:
                page_text = pytesseract.image_to_string(image)
                if page_text:
                    text_parts.append(page_text)

            text = "\n\n".join(text_parts)
            word_count = len(text.split())

            return ExtractionResult(
                text=text,
                method="ocr",
                word_count=word_count,
                page_count=page_count,
                success=True,
            )

        except Exception as e:
            return ExtractionResult(
                text="",
                method="ocr",
                word_count=0,
                page_count=0,
                success=False,
                error=str(e),
            )

    def extract_text(self, pdf_path: str) -> ExtractionResult:
        """
        Extract text from PDF, trying both methods and returning the better result.

        Args:
            pdf_path: Path to PDF file

        Returns:
            ExtractionResult with the best extraction
        """
        # Verify file exists
        if not os.path.exists(pdf_path):
            return ExtractionResult(
                text="",
                method="none",
                word_count=0,
                page_count=0,
                success=False,
                error=f"File not found: {pdf_path}",
            )

        # Try direct extraction first
        direct_result = self._extract_direct(pdf_path)

        # If direct extraction worked well (>100 words), use it
        if direct_result.success and direct_result.word_count > 100:
            return direct_result

        # Try OCR if enabled
        if self.ocr_enabled:
            ocr_result = self._extract_ocr(pdf_path)

            # Compare results and return the better one
            if ocr_result.success:
                if direct_result.success:
                    # Return whichever has more words
                    if ocr_result.word_count > direct_result.word_count:
                        return ocr_result
                    return direct_result
                return ocr_result

        # Return direct result (may be empty or failed)
        return direct_result

    def extract_batch(
        self,
        pdf_paths: list[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[ExtractionResult]:
        """
        Extract text from multiple PDFs.

        Args:
            pdf_paths: List of PDF file paths
            progress_callback: Optional callback(current, total, status)

        Returns:
            List of ExtractionResults
        """
        results = []
        total = len(pdf_paths)

        for i, pdf_path in enumerate(pdf_paths):
            filename = os.path.basename(pdf_path)
            if progress_callback:
                progress_callback(i, total, f"Extracting: {filename}")

            result = self.extract_text(pdf_path)
            results.append(result)

        if progress_callback:
            progress_callback(total, total, "Extraction complete")

        return results

    def get_extraction_summary(self, results: list[ExtractionResult]) -> dict:
        """
        Get summary statistics for batch extraction.

        Args:
            results: List of extraction results

        Returns:
            Summary dictionary
        """
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        methods = {"direct": 0, "ocr": 0, "combined": 0}
        for r in successful:
            methods[r.method] = methods.get(r.method, 0) + 1

        total_words = sum(r.word_count for r in successful)
        avg_words = total_words / len(successful) if successful else 0

        return {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "methods_used": methods,
            "total_words": total_words,
            "average_words": avg_words,
            "errors": [r.error for r in failed if r.error],
        }


class PDFBatchProcessor:
    """Process multiple PDFs from a directory."""

    def __init__(self, processor: Optional[PDFProcessor] = None):
        """
        Initialize batch processor.

        Args:
            processor: PDFProcessor instance (creates default if None)
        """
        self.processor = processor or PDFProcessor()

    def process_directory(
        self,
        directory: str | Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict[str, ExtractionResult]:
        """
        Process all PDFs in a directory.

        Args:
            directory: Directory containing PDFs
            progress_callback: Optional progress callback

        Returns:
            Dictionary mapping filename to ExtractionResult
        """
        directory = Path(directory)
        pdf_files = list(directory.glob("*.pdf"))

        results = {}
        total = len(pdf_files)

        for i, pdf_path in enumerate(pdf_files):
            if progress_callback:
                progress_callback(i, total, f"Processing: {pdf_path.name}")

            result = self.processor.extract_text(str(pdf_path))
            results[pdf_path.name] = result

        if progress_callback:
            progress_callback(total, total, "Processing complete")

        return results

    def match_pdfs_to_studies(
        self,
        pdf_results: dict[str, ExtractionResult],
        studies: list,
        match_by: str = "pmid",
    ) -> dict[str, Optional[ExtractionResult]]:
        """
        Match PDF extraction results to study objects.

        Args:
            pdf_results: Dictionary of filename -> ExtractionResult
            studies: List of Study objects
            match_by: Field to match on ("pmid", "doi", "title")

        Returns:
            Dictionary mapping study_id to ExtractionResult (or None if not found)
        """
        matched = {}

        for study in studies:
            match_value = getattr(study, match_by, None)
            if not match_value:
                matched[study.id] = None
                continue

            # Try to find matching PDF
            found = False
            for filename, result in pdf_results.items():
                # Check if match value appears in filename
                if str(match_value).lower() in filename.lower():
                    matched[study.id] = result
                    found = True
                    break

            if not found:
                matched[study.id] = None

        return matched

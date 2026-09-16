"""OCR abstraction. `extract_document_text` distinguishes text vs scanned docs.

Provider can be swapped later; rest of the app only depends on this interface.
"""
from __future__ import annotations

import io
import time
import os
import re
import shutil
from pathlib import Path
from sahlha.app.config import settings
from dataclasses import dataclass


@dataclass
class ExtractedDocument:
    text: str
    num_pages: int
    is_scanned: bool  # True when native text extraction yielded ~nothing (image-based)
    method: str       # e.g. "pypdf" | "docx" | "txt" | "ocr:tesseract" | "ocr:unavailable"


def _extract_pdf_native(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts), len(reader.pages)


def _extract_docx(data: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    parts.extend("\t".join(cell.text for cell in row.cells)
                 for table in doc.tables for row in table.rows)
    return "\n".join(parts)


def _extract_pptx(data: bytes) -> str:
    from pptx import Presentation

    presentation = Presentation(io.BytesIO(data))
    parts: list[str] = []
    for slide in presentation.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text)
            if shape.has_table:
                parts.extend("\t".join(cell.text for cell in row.cells)
                             for row in shape.table.rows)
    return "\n".join(parts)



def discover_tesseract():
    found = shutil.which("tesseract")
    if found:
        return found
    candidates = [settings.tesseract_cmd]
    for root in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
        if root:
            candidates.append(str(Path(root) / "Tesseract-OCR" / "tesseract.exe"))
    return next((p for p in candidates if p and Path(p).is_file()), None)


def discover_poppler():
    found = shutil.which("pdftoppm")
    if found:
        return str(Path(found).parent)
    candidates = [Path(settings.poppler_path)] if settings.poppler_path else []
    root = os.environ.get("ProgramFiles", "")
    if root:
        candidates.extend(Path(root).glob("poppler*/Library/bin"))
        candidates.extend(Path(root).glob("poppler*/bin"))
    return next((str(p) for p in candidates if any((p / name).is_file() for name in ("pdftoppm", "pdftoppm.exe"))), None)

def _try_ocr_images(data: bytes, suffix: str) -> tuple[str, str]:
    """Best-effort OCR via tesseract. Returns (text, method)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", "ocr:unavailable (pytesseract/Pillow not installed)"
    try:
        binary = discover_tesseract()
        if binary:
            pytesseract.pytesseract.tesseract_cmd = binary
        poppler = discover_poppler()
        if suffix == ".pdf":
            try:
                from pdf2image import convert_from_bytes, pdfinfo_from_bytes
            except ImportError:
                return "", "ocr:unavailable (pdf2image not installed)"
            deadline = time.monotonic() + 45
            pages = int(pdfinfo_from_bytes(data, timeout=10, poppler_path=poppler)["Pages"])
            texts = []
            for page in range(1, pages + 1):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("OCR exceeded 45 seconds; try a smaller scan")
                images = convert_from_bytes(data, dpi=150, first_page=page,
                                            last_page=page, timeout=remaining, poppler_path=poppler)
                try:
                    for image in images:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError("OCR exceeded 45 seconds; try a smaller scan")
                        texts.append(pytesseract.image_to_string(image, timeout=remaining))
                finally:
                    for image in images:
                        image.close()
            return "\n".join(texts), "ocr:tesseract(pdf2image)"
        with Image.open(io.BytesIO(data)) as image:
            return pytesseract.image_to_string(image, timeout=45), "ocr:tesseract"
    except Exception as exc:  # OCR is best-effort; never crash ingestion
        if type(exc).__name__ in {"TesseractNotFoundError", "PDFInfoNotInstalledError"}:
            return "", "ocr:unavailable"
        return "", "ocr:failed (try a smaller scan)"


def extract_document_text(file_bytes: bytes, filename: str) -> ExtractedDocument:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == ".pdf":
        text, pages = _extract_pdf_native(file_bytes)
        meaningful = re.sub(r"[^\w]", "", text)
        # A short, complete native sentence is useful even on a tiny handout.
        complete_short_text = len(text.split()) >= 5 and text.rstrip().endswith((".", "!", "?"))
        if len(meaningful) >= settings.ocr_min_chars or complete_short_text:
            return ExtractedDocument(text=text.strip(), num_pages=pages, is_scanned=False, method="pypdf")
        ocr_text, method = _try_ocr_images(file_bytes, ".pdf")
        if ocr_text.strip():
            return ExtractedDocument(text=ocr_text.strip(), num_pages=pages, is_scanned=True, method=method)
        return ExtractedDocument(text=text.strip(), num_pages=pages, is_scanned=True, method=method)
    if suffix == ".docx":
        return ExtractedDocument(text=_extract_docx(file_bytes).strip(), num_pages=1, is_scanned=False, method="docx")
    if suffix == ".pptx":
        return ExtractedDocument(text=_extract_pptx(file_bytes).strip(), num_pages=1, is_scanned=False, method="pptx")
    if suffix in {".txt", ".md", ""}:
        return ExtractedDocument(text=file_bytes.decode("utf-8", errors="ignore").strip(),
                                 num_pages=1, is_scanned=False, method="txt")
    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        ocr_text, method = _try_ocr_images(file_bytes, suffix)
        return ExtractedDocument(text=ocr_text.strip(), num_pages=1, is_scanned=True, method=method)
    # Fallback: try raw decode
    return ExtractedDocument(text=file_bytes.decode("utf-8", errors="ignore").strip(),
                             num_pages=1, is_scanned=False, method="raw")

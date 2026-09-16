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
from dataclasses import dataclass, field
from sahlha.app.rag.document import DocumentBlock, text_blocks, text_quality


@dataclass
class ExtractedDocument:
    text: str
    num_pages: int
    is_scanned: bool  # True when native text extraction yielded ~nothing (image-based)
    method: str       # e.g. "pypdf" | "docx" | "txt" | "ocr:tesseract" | "ocr:unavailable"
    blocks: list[DocumentBlock] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quality: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.blocks:
            self.blocks = text_blocks(self.text)
        score = text_quality(self.text)
        if score < .65 or not self.text.strip():
            self.warnings.append("Extraction quality is low; review source or OCR output.")
        self.quality = {"method": self.method, "pages": self.num_pages,
                        "ocr_used": self.is_scanned, "extracted_character_count": len(self.text),
                        "warnings": self.warnings, "quality_indicator": score}



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
        from PIL import Image, ImageOps, ImageEnhance
    except ImportError:
        return "", "ocr:unavailable (pytesseract/Pillow not installed)"
    try:
        def read_image(image, timeout):
            # Non-Pillow renderer adapters can still be passed to Tesseract.
            if not isinstance(image, Image.Image):
                return pytesseract.image_to_string(image, lang=settings.ocr_languages,
                    config="--psm 3 -c preserve_interword_spaces=1", timeout=timeout)
            image = ImageOps.exif_transpose(image)
            try:
                orientation = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT, timeout=min(5, timeout))
                if orientation.get("orientation_conf", 0) >= 5:
                    image = image.rotate(-orientation.get("rotate", 0), expand=True)
            except Exception:
                pass
            image = ImageOps.autocontrast(ImageOps.grayscale(image))
            return pytesseract.image_to_string(image, lang=settings.ocr_languages,
                config="--psm 3 -c preserve_interword_spaces=1", timeout=timeout)

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
                images = convert_from_bytes(data, dpi=max(150, min(settings.ocr_dpi, 400)), first_page=page,
                                            last_page=page, timeout=remaining, poppler_path=poppler)
                try:
                    for image in images:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError("OCR exceeded 45 seconds; try a smaller scan")
                        texts.append(read_image(image, remaining))
                finally:
                    for image in images:
                        image.close()
            return "\n".join(texts), "ocr:tesseract(pdf2image)"
        with Image.open(io.BytesIO(data)) as image:
            return read_image(image, 45), "ocr:tesseract"
    except Exception as exc:  # OCR is best-effort; never crash ingestion
        if type(exc).__name__ in {"TesseractNotFoundError", "PDFInfoNotInstalledError"}:
            return "", "ocr:unavailable"
        return "", "ocr:failed (try a smaller scan)"


def extract_document_text(file_bytes: bytes, filename: str) -> ExtractedDocument:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == ".pdf":
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(io.BytesIO(file_bytes))
        blocks, texts, warnings, methods = [], [], [], []
        scanned = False
        for number, page in enumerate(reader.pages, 1):
            try:
                try:
                    native = page.extract_text(extraction_mode="layout") or ""
                except TypeError:
                    native = page.extract_text() or ""
            except Exception:
                native = ""
            meaningful = re.sub(r"[^\w]", "", native)
            good = text_quality(native) >= .65 and (len(meaningful) >= settings.ocr_min_chars or
                (len(native.split()) >= 5 and native.rstrip().endswith((".", "!", "?"))))
            method, text = "pypdf", native
            if not good:
                scanned = True
                writer = PdfWriter()
                writer.add_page(page)
                stream = io.BytesIO()
                writer.write(stream)
                recovered, method = _try_ocr_images(stream.getvalue(), ".pdf")
                if recovered.strip() and text_quality(recovered) >= text_quality(native):
                    text = recovered
                if not recovered.strip() or text_quality(text) < .65:
                    warnings.append(f"Low OCR quality on page {number} ({method}).")
            texts.append(text.strip())
            blocks.extend(text_blocks(text, number))
            methods.append(method)
        method = methods[0] if len(set(methods)) == 1 else "hybrid:pypdf+tesseract"
        return ExtractedDocument("\n".join(texts), len(reader.pages), scanned, method,
                                 blocks=blocks, warnings=warnings)
    if suffix == ".docx":
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        document = Document(io.BytesIO(file_bytes))
        blocks = []
        for element in document.element.body.iterchildren():
            if element.tag.endswith('}tbl'):
                table = Table(element, document)
                text = '\n'.join('\t'.join(c.text for c in row.cells) for row in table.rows)
                blocks.append(DocumentBlock(1, len(blocks), 'table', text))
            elif element.tag.endswith('}p'):
                paragraph = Paragraph(element, document)
                if not paragraph.text.strip() and not paragraph._p.xpath('.//m:oMath'):
                    continue
                style = paragraph.style.name.lower() if paragraph.style else ''
                monospace = any((run.font.name or '').lower() in {'consolas', 'courier new', 'courier', 'monospace'} for run in paragraph.runs)
                kind = ('heading' if 'heading' in style or style == 'title' else
                        'list' if 'list' in style or paragraph._p.xpath('./w:pPr/w:numPr') else
                        'code' if monospace or any(x in style for x in ('code', 'preformatted')) else 'paragraph')
                paragraph_text = ''.join(node.text or '' for node in paragraph._p.iter()
                    if node.tag.endswith('}t')) if paragraph._p.xpath('.//m:oMath') else paragraph.text
                if paragraph._p.xpath('.//m:oMath') and not paragraph.text.strip():
                    kind = 'formula'
                blocks.append(DocumentBlock(1, len(blocks), kind, paragraph_text,
                                             {'style': style, 'page_is_logical': True}))
        return ExtractedDocument('\n'.join(b.text for b in blocks), 1, False, 'docx', blocks)
    if suffix == ".pptx":
        from pptx import Presentation
        presentation = Presentation(io.BytesIO(file_bytes))
        blocks = []
        for number, slide in enumerate(presentation.slides, 1):
            for shape in sorted(slide.shapes, key=lambda s: (s.top, s.left)):
                if shape.has_table:
                    text = '\n'.join('\t'.join(c.text for c in row.cells) for row in shape.table.rows)
                    blocks.append(DocumentBlock(number, len(blocks), 'table', text))
                elif shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        if paragraph.text.strip():
                            kind = 'heading' if shape == slide.shapes.title else 'list' if paragraph.level else 'paragraph'
                            blocks.append(DocumentBlock(number, len(blocks), kind, paragraph.text))
        return ExtractedDocument('\n'.join(b.text for b in blocks), len(presentation.slides), False, 'pptx', blocks)
    if suffix in {".txt", ".md", ""}:
        return ExtractedDocument(text=file_bytes.decode("utf-8", errors="ignore").strip(),
                                 num_pages=1, is_scanned=False, method="txt")
    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        ocr_text, method = _try_ocr_images(file_bytes, suffix)
        return ExtractedDocument(text=ocr_text.strip(), num_pages=1, is_scanned=True, method=method)
    # Fallback: try raw decode
    return ExtractedDocument(text=file_bytes.decode("utf-8", errors="ignore").strip(),
                             num_pages=1, is_scanned=False, method="raw")

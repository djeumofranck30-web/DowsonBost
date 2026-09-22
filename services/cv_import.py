"""Import CV text from PDF, DOCX or plain text without extra heavy parsers."""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree as ET

from constants import MIN_CV_TEXT_LENGTH

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def detect_document_kind(data: bytes, filename: str = "") -> str:
    """Return ``pdf``, ``docx``, ``txt`` or ``unknown``."""
    name = (filename or "").strip().lower()
    if name.endswith(".docx"):
        return "docx"
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".txt"):
        return "txt"
    head = bytes(data or b"")[:8]
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK") and _zip_has_word_document(data):
        return "docx"
    try:
        sample = bytes(data or b"")[:4000].decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    if sample.strip():
        return "txt"
    return "unknown"


def _zip_has_word_document(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return False


def extract_docx_text(data: bytes) -> str:
    """Read paragraph text from a Word .docx (Office Open XML)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, OSError, zipfile.BadZipFile) as exc:
        raise RuntimeError("Fichier DOCX illisible.") from exc
    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_W_NS}p"):
        parts = [node.text or "" for node in paragraph.iter(f"{_W_NS}t")]
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    from cv_layout import normalize_extracted_cv_text

    return normalize_extracted_cv_text("\n".join(paragraphs))


def extract_plain_text(data: bytes) -> str:
    from cv_layout import normalize_extracted_cv_text

    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return normalize_extracted_cv_text(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    return normalize_extracted_cv_text(data.decode("utf-8", errors="ignore"))


def extract_document_text(data: bytes, filename: str = "") -> tuple[str, str]:
    """Extract candidate text and the method used (``docx``, ``txt``, or empty).

    PDF extraction stays in ``app.extract_cv_text`` (native + OCR).
    """
    kind = detect_document_kind(data, filename)
    if kind == "docx":
        text = extract_docx_text(data)
        if len(text) < MIN_CV_TEXT_LENGTH:
            raise RuntimeError(
                "Impossible d'extraire suffisamment de texte du DOCX."
            )
        return text, "docx"
    if kind == "txt":
        text = extract_plain_text(data)
        if len(text) < MIN_CV_TEXT_LENGTH:
            raise RuntimeError("Le fichier texte du CV est trop court.")
        return text, "txt"
    return "", kind

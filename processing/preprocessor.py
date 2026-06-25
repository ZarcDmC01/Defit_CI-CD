from __future__ import annotations
import io


class PreprocessingError(Exception):
    pass


def extract_text(content: bytes, filename: str) -> str:
    """Extract plain text from TXT or PDF bytes."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if suffix == "txt":
        return _extract_txt(content)
    if suffix == "pdf":
        return _extract_pdf(content)

    raise PreprocessingError(f"Cannot extract text from '.{suffix}' files.")


def _extract_txt(content: bytes) -> str:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = content.decode(encoding).strip()
            if text:
                return text
        except (UnicodeDecodeError, ValueError):
            continue
    raise PreprocessingError("Could not decode text file with supported encodings.")


def _extract_pdf(content: bytes) -> str:
    try:
        import pypdf  # lazy import — only needed for PDF
    except ImportError as exc:
        raise PreprocessingError("pypdf is required for PDF processing.") from exc

    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
    except Exception as exc:
        raise PreprocessingError(f"Failed to parse PDF: {exc}") from exc

    if not text:
        raise PreprocessingError("PDF contains no extractable text (may be scanned/image-only).")

    return text

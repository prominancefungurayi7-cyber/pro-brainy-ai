"""Bounded extraction of text supplied to the short-form Gemini tools."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import docx
import PyPDF2


MAX_AI_TEXT_CHARS = 20_000
MAX_PDF_PAGES = 50
MAX_DOCX_MEMBERS = 2_000
MAX_DOCX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024


class UploadTextError(ValueError):
    """A safe, actionable error for a user-supplied text or file."""


def check_text_length(text):
    if text and len(text) > MAX_AI_TEXT_CHARS:
        raise UploadTextError(
            'This text is too long for one request. Use 20,000 characters or fewer.'
        )
    return text


def _paragraphs_in_order(container):
    for block in container.iter_inner_content():
        if isinstance(block, docx.text.paragraph.Paragraph):
            yield block
        else:
            seen_cells = set()
            for row in block.rows:
                for cell in row.cells:
                    if id(cell._tc) not in seen_cells:
                        seen_cells.add(id(cell._tc))
                        yield from _paragraphs_in_order(cell)


def _read_pdf(content):
    if not content.startswith(b'%PDF-'):
        raise UploadTextError('Please upload a valid PDF file.')
    try:
        reader = PyPDF2.PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise UploadTextError('Unlock this PDF before uploading it.')
        if len(reader.pages) > MAX_PDF_PAGES:
            raise UploadTextError('This PDF is too long. Use 50 pages or fewer.')
        parts = []
        length = 0
        for page in reader.pages:
            page_text = page.extract_text() or ''
            length += len(page_text) + (1 if parts else 0)
            if length > MAX_AI_TEXT_CHARS:
                raise UploadTextError(
                    'This text is too long for one request. Use 20,000 characters or fewer.'
                )
            parts.append(page_text)
    except UploadTextError:
        raise
    except Exception as exc:
        raise UploadTextError('Please upload a valid PDF file.') from exc
    text = '\n'.join(parts).strip()
    if not text:
        raise UploadTextError(
            'This PDF has no selectable text. A scanned PDF needs OCR before processing.'
        )
    return text


def _read_docx(content):
    try:
        with ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if (
                len(members) > MAX_DOCX_MEMBERS
                or sum(member.file_size for member in members) > MAX_DOCX_UNCOMPRESSED_BYTES
            ):
                raise UploadTextError('This Word file is too large to process safely.')
        document = docx.Document(BytesIO(content))
        parts = []
        length = 0
        for paragraph in _paragraphs_in_order(document):
            if paragraph.text.strip():
                length += len(paragraph.text) + (1 if parts else 0)
                if length > MAX_AI_TEXT_CHARS:
                    raise UploadTextError(
                        'This text is too long for one request. Use 20,000 characters or fewer.'
                    )
                parts.append(paragraph.text)
    except UploadTextError:
        raise
    except Exception as exc:
        raise UploadTextError('Please upload a valid .docx file.') from exc
    text = '\n'.join(parts).strip()
    if not text:
        raise UploadTextError(
            'This Word file has no selectable text. Images need OCR before processing.'
        )
    return text


def _read_txt(content):
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise UploadTextError('Please save this text file as UTF-8 and try again.') from exc
    if any(ord(char) < 32 and char not in '\n\r\t' for char in text):
        raise UploadTextError('This file does not contain plain text.')
    return check_text_length(text.strip())


def read_uploaded_text(file_storage, *, allow_docx=False):
    """Read only supported file types, with clear limits before AI generation."""
    if not file_storage or not file_storage.filename:
        return None
    suffix = Path(file_storage.filename).suffix.casefold()
    allowed = {'.txt', '.pdf', '.docx'} if allow_docx else {'.txt', '.pdf'}
    if suffix not in allowed:
        options = ', '.join(sorted(allowed))
        raise UploadTextError(f'Upload one of these file types: {options}.')
    content = file_storage.read()
    if not content:
        raise UploadTextError('The uploaded file is empty.')
    if suffix == '.pdf':
        return _read_pdf(content)
    if suffix == '.docx':
        return _read_docx(content)
    return _read_txt(content)

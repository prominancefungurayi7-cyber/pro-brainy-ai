"""Optional live check for the document humanizer and writing review."""

import argparse
import base64
import sys
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.shared import Inches

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.detector_service import detect_ai  # noqa: E402
from services.humanizer_service import humanize_docx, humanize_text  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Run three small live Gemini checks.')
    parser.add_argument('--live', action='store_true', help='Required to call Gemini.')
    args = parser.parse_args()
    if not args.live:
        parser.error('Pass --live to make Gemini API calls.')

    source_text = (
        'The project proposal will be considered by the team. It is important '
        'to note that this plan is designed to facilitate collaboration.'
    )
    text_result = humanize_text(source_text)
    if not text_result.strip() or text_result == source_text:
        raise RuntimeError('Plain text humanization returned no rewrite.')
    print('humanizer text: OK', flush=True)

    document = Document()
    document.add_heading('Project proposal', level=1)
    document.add_paragraph(source_text)
    image = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9pLFsAAAAASUVORK5CYII='
    )
    illustrated = document.add_paragraph()
    illustrated.add_run('Illustration: ')
    illustrated.add_run().add_picture(BytesIO(image), width=Inches(.2))
    illustrated.add_run(' the original image.')
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = 'The team will review the proposal.'
    source_file = BytesIO()
    document.save(source_file)
    result = Document(humanize_docx(source_file.getvalue()))
    if result.paragraphs[0].text != 'Project proposal':
        raise RuntimeError('Word heading changed.')
    if not result.paragraphs[1].text.strip() or not result.tables[0].cell(0, 0).text.strip():
        raise RuntimeError('Word body text was lost.')
    if (
        result.paragraphs[1].text == source_text
        and result.tables[0].cell(0, 0).text == 'The team will review the proposal.'
    ):
        raise RuntimeError('Word body text was not rewritten.')
    if len(result.tables) != 1:
        raise RuntimeError('Word table was lost.')
    if len(result.inline_shapes) != 1 or result.paragraphs[2].text != 'Illustration:  the original image.':
        raise RuntimeError('Word image or its surrounding text changed.')
    if image not in (part.blob for part in result.part.related_parts.values()):
        raise RuntimeError('Word image bytes changed.')
    print('humanizer Word: OK', flush=True)

    review = detect_ai('The team reviewed the proposal and made a few changes.')
    if 'cannot determine' not in review.lower():
        raise RuntimeError('Writing review returned an incomplete explanation.')
    print('writing review: OK', flush=True)


if __name__ == '__main__':
    main()

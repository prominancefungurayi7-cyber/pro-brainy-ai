"""Optional live end-to-end PowerPoint download check."""

import argparse
import os
import sys
from io import BytesIO
from pathlib import Path

from pptx import Presentation

os.environ['FLASK_TESTING'] = '1'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'local-ppt-smoke-only'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app  # noqa: E402
from tests.helpers import csrf_token, register_client  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Exercise the PowerPoint route with live Gemini.')
    parser.add_argument('--live', action='store_true', help='Required to call Gemini.')
    args = parser.parse_args()
    if not args.live:
        parser.error('Pass --live to make Gemini API calls.')
    client = app.test_client()
    register_client(client)
    response = client.post('/ppt/download', data={
        '_csrf_token': csrf_token(client),
        'topic': 'The water cycle', 'audience': 'Secondary school learners',
        'slides': '4', 'detail_level': 'fully_explanatory',
        'include_diagrams': 'on',
    }, headers={'Accept': 'application/json'})
    if response.status_code != 200:
        raise RuntimeError(f'PowerPoint request failed ({response.status_code}): {response.get_json()}')
    if 'presentationml.presentation' not in response.content_type:
        raise RuntimeError('The server did not return a PowerPoint file.')
    deck = Presentation(BytesIO(response.data))
    if len(deck.slides) != 4:
        raise RuntimeError('The downloaded PowerPoint has the wrong slide count.')
    for slide in list(deck.slides)[1:]:
        if not slide.notes_slide.notes_text_frame.text.strip():
            raise RuntimeError('A content slide has no presenter notes.')
    pictures = sum(
        shape.shape_type == 13 for slide in deck.slides for shape in slide.shapes
    )
    print(f'PowerPoint download: OK (4 slides, {pictures} licensed internet diagrams)', flush=True)


if __name__ == '__main__':
    main()

"""Optional end-to-end Word stream check against live Gemini, using an in-memory account."""

import argparse
import base64
import hashlib
import json
import os
from io import BytesIO
from pathlib import Path
import sys

from docx import Document
from docx.shared import Inches

os.environ['FLASK_TESTING'] = '1'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'local-smoke-test-only'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app  # noqa: E402
from tests.helpers import csrf_token, register_client  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Exercise the HTTP Word stream with live Gemini.')
    parser.add_argument('--live', action='store_true', help='Required to call Gemini.')
    if not parser.parse_args().live:
        parser.error('Pass --live to make a Gemini API call.')

    image = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9pLFsAAAAASUVORK5CYII='
    )
    document = Document()
    document.add_heading('Project plan', level=1)
    source_body = 'The team will discuss the proposal and decide what to do next.'
    document.add_paragraph(source_body)
    mixed = document.add_paragraph()
    mixed.add_run('Figure: ')
    mixed.add_run().add_picture(BytesIO(image), width=Inches(.2))
    mixed.add_run(' keep this image.')
    source = BytesIO()
    document.save(source)

    client = app.test_client()
    register_client(client)
    response = client.post('/humanizer', data={
        '_csrf_token': csrf_token(client),
        'file': (BytesIO(source.getvalue()), 'project.docx'),
    }, content_type='multipart/form-data', headers={'Accept': 'text/event-stream'})
    if response.status_code != 200:
        raise RuntimeError(f'HTTP stream failed with status {response.status_code}.')
    events = [
        json.loads(frame[6:])
        for frame in response.data.decode().split('\n\n')
        if frame.startswith('data: ')
    ]
    if any(event['type'] == 'error' for event in events):
        raise RuntimeError('HTTP stream returned a document error.')
    if not events or events[-1]['type'] != 'complete':
        raise RuntimeError('HTTP stream ended without completion.')
    start = next(event for event in events if event['type'] == 'file-start')
    content = b''.join(
        base64.b64decode(event['data'])
        for event in events if event['type'] == 'file-chunk'
    )
    if len(content) != start['size'] or hashlib.sha256(content).hexdigest() != start['sha256']:
        raise RuntimeError('HTTP stream returned an incomplete Word file.')
    result = Document(BytesIO(content))
    if result.paragraphs[0].text != 'Project plan' or result.paragraphs[1].text == source_body:
        raise RuntimeError('Heading changed or body was not rewritten.')
    if len(result.inline_shapes) != 1 or result.paragraphs[2].text != 'Figure:  keep this image.':
        raise RuntimeError('Word image or surrounding text changed.')
    print('HTTP Word stream: OK', flush=True)


if __name__ == '__main__':
    main()

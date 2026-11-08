import base64
import hashlib
import json
import threading
import unittest
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Inches

from app import app
from models.user import db
from services.gemini_service import GeminiGenerationError
from tests.helpers import csrf_token, register_client


def sample_document():
    doc = Document()
    doc.add_heading('Introduction', level=1)
    doc.add_paragraph().add_run('Manually bold heading').bold = True
    doc.add_paragraph('Original first body.')
    table = doc.add_table(rows=2, cols=1)
    table.cell(0, 0).paragraphs[0].style = 'Heading 2'
    table.cell(0, 0).paragraphs[0].text = 'Table heading'
    table.cell(1, 0).paragraphs[0].text = 'Original table body.'
    doc.add_paragraph('Original last body.')
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


class DocxHumanizerTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
        register_client(self.client)
        self.client.get('/humanizer')

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    @patch('services.humanizer_service.generate_response')
    def test_docx_preserves_order_headings_and_table(self, mock_ai):
        def rewrite(prompt, **kwargs):
            source = json.loads(prompt.split('\n')[-1])
            rewritten_text = ' '.join(item['text'] for item in source)
            self.assertNotIn('Introduction', rewritten_text)
            self.assertNotIn('Table heading', rewritten_text)
            self.assertNotIn('Manually bold heading', rewritten_text)
            self.assertIn('READ-ONLY CONTEXT', prompt)
            self.assertNotIn('primary school', prompt.lower())
            self.assertIn('I keep my sentences short.', prompt)
            self.assertEqual(kwargs['config']['response_mime_type'], 'application/json')
            self.assertTrue(kwargs['raise_on_error'])
            return json.dumps([{'id': item['id'], 'text': item['text'] + ' Humanized.'} for item in source])

        mock_ai.side_effect = rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'voice_sample': 'I keep my sentences short.',
            'file': (BytesIO(sample_document()), 'sample.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertIn('sample_humanized.docx', response.headers['Content-Disposition'])
        result = Document(BytesIO(response.data))
        self.assertEqual(result.paragraphs[0].text, 'Introduction')
        self.assertEqual(result.paragraphs[1].text, 'Manually bold heading')
        self.assertEqual(result.paragraphs[2].text, 'Original first body. Humanized.')
        self.assertEqual(result.tables[0].cell(0, 0).text, 'Table heading')
        self.assertEqual(result.tables[0].cell(1, 0).text, 'Original table body. Humanized.')
        self.assertEqual(result.paragraphs[3].text, 'Original last body. Humanized.')
        self.assertEqual(result.paragraphs[0].style.name, 'Heading 1')

    @patch('services.humanizer_service.generate_response')
    def test_stream_reports_measured_progress_and_downloads_valid_docx(self, mock_ai):
        def rewrite(prompt, **_kwargs):
            self.assertIn('I use plain words.', prompt)
            source = json.loads(prompt.split('\n')[-1])
            return json.dumps([{'id': item['id'], 'text': item['text'] + ' Revised.'} for item in source])

        mock_ai.side_effect = rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'voice_sample': 'I use plain words.',
            'file': (BytesIO(sample_document()), 'sample.docx'),
        }, content_type='multipart/form-data', headers={'Accept': 'text/event-stream'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/event-stream', response.content_type)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        events = [json.loads(frame[6:]) for frame in response.data.decode().split('\n\n') if frame]
        progress = [event['percent'] for event in events if event['type'] == 'progress']
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[0], 0)
        self.assertEqual(progress[-1], 95)
        self.assertEqual(events[-1], {'type': 'complete', 'percent': 100})
        self.assertEqual(next(event['filename'] for event in events if event['type'] == 'file-start'), 'sample_humanized.docx')
        data = b''.join(base64.b64decode(event['data']) for event in events if event['type'] == 'file-chunk')
        file_start = next(event for event in events if event['type'] == 'file-start')
        self.assertEqual(file_start['size'], len(data))
        self.assertEqual(file_start['sha256'], hashlib.sha256(data).hexdigest())
        document = Document(BytesIO(data))
        self.assertEqual(document.paragraphs[0].text, 'Introduction')
        self.assertEqual(document.paragraphs[2].text, 'Original first body. Revised.')

    @patch('routes.humanizer_routes.STREAM_KEEPALIVE_SECONDS', 0.02)
    @patch('services.humanizer_service.generate_response')
    def test_stream_stays_open_while_first_ai_batch_is_waiting(self, mock_ai):
        release_ai = threading.Event()
        ai_started = threading.Event()

        def delayed_rewrite(prompt, **_kwargs):
            ai_started.set()
            self.assertTrue(release_ai.wait(2), 'The test did not release the AI batch')
            source = json.loads(prompt.split('\n')[-1])
            return json.dumps([{'id': item['id'], 'text': item['text'] + ' Revised.'} for item in source])

        mock_ai.side_effect = delayed_rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(sample_document()), 'sample.docx'),
        }, content_type='multipart/form-data', headers={'Accept': 'text/event-stream'}, buffered=False)
        frames = iter(response.response)
        try:
            initial = []
            while len(initial) < 3:
                frame = next(frames).decode()
                if frame.startswith('data: '):
                    initial.append(frame)
            self.assertEqual([json.loads(frame[6:])['percent'] for frame in initial], [0, 5, 10])
            self.assertTrue(ai_started.wait(1))
            self.assertEqual(next(frames), b': keep-alive\n\n')
        finally:
            release_ai.set()
        rest = b''.join(frames).decode()
        events = [json.loads(frame[6:]) for frame in rest.split('\n\n') if frame.startswith('data: ')]
        self.assertEqual(events[-1], {'type': 'complete', 'percent': 100})
        file_bytes = b''.join(base64.b64decode(event['data']) for event in events if event['type'] == 'file-chunk')
        self.assertEqual(Document(BytesIO(file_bytes)).paragraphs[2].text, 'Original first body. Revised.')

    @patch('services.humanizer_service.generate_response', side_effect=GeminiGenerationError('AI service unavailable'))
    def test_stream_failure_does_not_send_partial_word_file(self, _mock_ai):
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(sample_document()), 'sample.docx'),
        }, content_type='multipart/form-data', headers={'Accept': 'text/event-stream'})
        events = [json.loads(frame[6:]) for frame in response.data.decode().split('\n\n') if frame]
        self.assertEqual(events[-1]['type'], 'error')
        self.assertFalse(any(event['type'] == 'file-chunk' for event in events))

    @patch('services.humanizer_service.generate_response', side_effect=GeminiGenerationError('AI service unavailable'))
    def test_docx_does_not_return_partial_file_on_ai_failure(self, _mock_ai):
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(sample_document()), 'sample.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 422)
        self.assertIn(b'AI service unavailable', response.data)
        self.assertNotIn('attachment', response.headers.get('Content-Disposition', ''))

    @patch('services.humanizer_service.generate_response')
    def test_docx_recovers_from_malformed_batch_by_rewriting_smaller_groups(self, mock_ai):
        def rewrite(prompt, **_kwargs):
            source = json.loads(prompt.split('\n')[-1])
            if len(source) > 1:
                return 'I cannot format this batch.'
            return json.dumps([{'id': 0, 'text': source[0]['text'] + ' Revised.'}])

        mock_ai.side_effect = rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(sample_document()), 'sample.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(mock_ai.call_count, 1)
        result = Document(BytesIO(response.data))
        self.assertEqual(result.paragraphs[0].text, 'Introduction')
        self.assertEqual(result.paragraphs[2].text, 'Original first body. Revised.')
        self.assertEqual(result.tables[0].cell(1, 0).text, 'Original table body. Revised.')

    def test_invalid_docx_is_rejected(self):
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(b'not a word document'), 'broken.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 422)

    @patch('services.humanizer_service.generate_response')
    def test_inherited_heading_and_mixed_formatting_are_preserved(self, mock_ai):
        document = Document()
        section_style = document.styles.add_style('Custom Section', WD_STYLE_TYPE.PARAGRAPH)
        section_style.base_style = document.styles['Heading 1']
        document.add_paragraph('A custom section title', style=section_style)
        mixed = document.add_paragraph()
        mixed.add_run('This is ')
        mixed.add_run('important').bold = True
        mixed.add_run(' body text.')
        document.add_paragraph('A plain body paragraph.')
        source = BytesIO()
        document.save(source)

        def rewrite(prompt, **_kwargs):
            items = json.loads(prompt.split('\n')[-1])
            self.assertEqual([item['text'] for item in items], ['A plain body paragraph.'])
            return json.dumps([{'id': 0, 'text': 'A clearer body paragraph.'}])

        mock_ai.side_effect = rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(source.getvalue()), 'styled.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        result = Document(BytesIO(response.data))
        self.assertEqual(result.paragraphs[0].text, 'A custom section title')
        self.assertEqual(result.paragraphs[1].text, 'This is important body text.')
        self.assertTrue(result.paragraphs[1].runs[1].bold)
        self.assertEqual(result.paragraphs[2].text, 'A clearer body paragraph.')

    @patch('services.humanizer_service.generate_response')
    def test_oversize_docx_is_rejected_before_ai_call(self, mock_ai):
        document = Document()
        for index in range(121):
            document.add_paragraph(f'Body paragraph {index}.')
        source = BytesIO()
        document.save(source)
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(source.getvalue()), 'large.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 422)
        self.assertIn(b'Split it into smaller Word files', response.data)
        mock_ai.assert_not_called()

    @patch('routes.humanizer_routes._DOCX_JOB_SLOTS')
    @patch('services.humanizer_service.generate_response')
    def test_busy_document_worker_returns_retry_message_without_ai_call(self, mock_ai, slots):
        slots.acquire.return_value = False
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(sample_document()), 'sample.docx'),
        }, content_type='multipart/form-data', headers={'Accept': 'text/event-stream'})
        events = [json.loads(frame[6:]) for frame in response.data.decode().split('\n\n') if frame]
        self.assertEqual(events, [{
            'type': 'error', 'message': 'Document processing is busy. Please try again shortly.',
        }])
        mock_ai.assert_not_called()
        slots.release.assert_not_called()

    @patch('routes.humanizer_routes._DOCX_JOB_SLOTS')
    @patch('services.humanizer_service.generate_response')
    def test_busy_sync_document_worker_returns_retry_message(self, mock_ai, slots):
        slots.acquire.return_value = False
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(sample_document()), 'sample.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 429)
        self.assertIn(b'Document processing is busy', response.data)
        mock_ai.assert_not_called()
        slots.release.assert_not_called()

    @patch('services.humanizer_service.generate_response')
    def test_images_and_text_position_survive_rewrite(self, mock_ai):
        image = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9pLFsAAAAASUVORK5CYII='
        )
        document = Document()
        document.add_heading('Project report', level=1)
        document.add_paragraph('Ordinary body text.')
        mixed = document.add_paragraph()
        mixed.add_run('Before image. ')
        mixed.add_run().add_picture(BytesIO(image), width=Inches(.25))
        mixed.add_run(' After image.')
        document.add_paragraph('Another body paragraph.')
        source_file = BytesIO()
        document.save(source_file)

        def rewrite(prompt, **_kwargs):
            source = json.loads(prompt.split('\n')[-1])
            self.assertNotIn('Before image', prompt)
            self.assertNotIn('After image', prompt)
            return json.dumps([{'id': item['id'], 'text': item['text'] + ' Revised.'}
                               for item in source])

        mock_ai.side_effect = rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(source_file.getvalue()), 'illustrated.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        result = Document(BytesIO(response.data))
        self.assertEqual([paragraph.text for paragraph in result.paragraphs], [
            'Project report', 'Ordinary body text. Revised.',
            'Before image.  After image.', 'Another body paragraph. Revised.',
        ])
        self.assertEqual(len(result.inline_shapes), 1)
        with ZipFile(BytesIO(source_file.getvalue())) as before, ZipFile(BytesIO(response.data)) as after:
            image_name = next(name for name in before.namelist() if name.startswith('word/media/'))
            self.assertEqual(before.read(image_name), after.read(image_name))
        self.assertEqual(mock_ai.call_count, 1)


if __name__ == '__main__':
    unittest.main()

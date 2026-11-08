import base64
import json
import unittest
from io import BytesIO
from unittest.mock import patch

from docx import Document

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
            self.assertNotIn('Introduction', prompt)
            self.assertNotIn('Table heading', prompt)
            self.assertNotIn('Manually bold heading', prompt)
            self.assertNotIn('primary school', prompt.lower())
            self.assertEqual(kwargs['config']['response_mime_type'], 'application/json')
            self.assertTrue(kwargs['raise_on_error'])
            return json.dumps([{'id': item['id'], 'text': item['text'] + ' Humanized.'} for item in source])

        mock_ai.side_effect = rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
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
            source = json.loads(prompt.split('\n')[-1])
            return json.dumps([{'id': item['id'], 'text': item['text'] + ' Revised.'} for item in source])

        mock_ai.side_effect = rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
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
        document = Document(BytesIO(data))
        self.assertEqual(document.paragraphs[0].text, 'Introduction')
        self.assertEqual(document.paragraphs[2].text, 'Original first body. Revised.')

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


if __name__ == '__main__':
    unittest.main()

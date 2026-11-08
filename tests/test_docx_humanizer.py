import json
import unittest
from io import BytesIO
from unittest.mock import patch

from docx import Document

from app import app
from models.user import db
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
        def rewrite(prompt):
            source = json.loads(prompt.split('\n')[-1])
            self.assertNotIn('Introduction', prompt)
            self.assertNotIn('Table heading', prompt)
            self.assertNotIn('Manually bold heading', prompt)
            return json.dumps([{'id': item['id'], 'text': item['text'] + ' Humanized.'} for item in source])

        mock_ai.side_effect = rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'education_level': 'O level',
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

    @patch('services.humanizer_service.generate_response', return_value='AI service unavailable')
    def test_docx_does_not_return_partial_file_on_ai_failure(self, _mock_ai):
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(sample_document()), 'sample.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('attachment', response.headers.get('Content-Disposition', ''))

    def test_invalid_docx_is_rejected(self):
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(b'not a word document'), 'broken.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()

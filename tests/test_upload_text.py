import unittest
from io import BytesIO
from unittest.mock import patch

from docx import Document
from PyPDF2 import PdfWriter

from app import app
from models.user import db
from tests.helpers import csrf_token, register_client


class UploadTextTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
        register_client(self.client)

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def _post_file(self, route, filename, content):
        return self.client.post(route, data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(content), filename),
        }, content_type='multipart/form-data')

    @patch('routes.detector_routes.detect_ai')
    @patch('routes.humanizer_routes.humanize_text')
    def test_unsupported_files_fail_before_ai(self, humanize, detect):
        for route in ('/humanizer', '/detector'):
            with self.subTest(route=route):
                response = self._post_file(route, 'photo.png', b'\x89PNG\r\n')
                self.assertEqual(response.status_code, 422)
                self.assertIn(b'Upload one of these file types', response.data)
        humanize.assert_not_called()
        detect.assert_not_called()

    @patch('routes.detector_routes.detect_ai')
    @patch('routes.humanizer_routes.humanize_text')
    def test_oversized_paste_fails_before_ai(self, humanize, detect):
        for route in ('/humanizer', '/detector'):
            with self.subTest(route=route):
                response = self.client.post(route, data={
                    '_csrf_token': csrf_token(self.client),
                    'text': 'a' * 20_001,
                })
                self.assertEqual(response.status_code, 422)
                self.assertIn(b'20,000 characters or fewer', response.data)
        humanize.assert_not_called()
        detect.assert_not_called()

    @patch('routes.detector_routes.detect_ai')
    def test_detector_reads_word_table_in_document_order(self, detect):
        document = Document()
        document.add_paragraph('Before table.')
        document.add_table(rows=1, cols=1).cell(0, 0).text = 'Table text.'
        document.add_paragraph('After table.')
        data = BytesIO()
        document.save(data)
        detect.return_value = 'Writing review.'

        response = self._post_file('/detector', 'document.docx', data.getvalue())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(detect.call_args.args[0],
                         'Before table.\nTable text.\nAfter table.')

    @patch('routes.detector_routes.detect_ai')
    def test_scanned_pdf_has_actionable_error(self, detect):
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        data = BytesIO()
        writer.write(data)

        response = self._post_file('/detector', 'scan.pdf', data.getvalue())
        self.assertEqual(response.status_code, 422)
        self.assertIn(b'needs OCR', response.data)
        detect.assert_not_called()

    @patch('routes.humanizer_routes.humanize_text')
    def test_invalid_utf8_text_is_rejected(self, humanize):
        response = self._post_file('/humanizer', 'notes.txt', b'\xff\xfe\x00')
        self.assertEqual(response.status_code, 422)
        self.assertIn(b'UTF-8', response.data)
        humanize.assert_not_called()


if __name__ == '__main__':
    unittest.main()

"""Tool pages must distinguish actionable errors from generated content."""

import unittest
from io import BytesIO
from unittest.mock import patch

from app import app
from models.user import db
from services.gemini_service import GeminiGenerationError
from tests.helpers import csrf_token, register_client


class ToolFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
        register_client(self.client)

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_gemini_failures_appear_as_errors_without_generated_output(self):
        cases = (
            ('/grammar', 'routes.grammar_routes.fix_grammar', {'text': 'Fix this sentence.'}),
            ('/essay', 'routes.essay_routes.generate_essay', {'topic': 'Rainfall'}),
            ('/composition', 'routes.composition_routes.generate_composition', {'topic': 'A trip'}),
            ('/summarizer', 'routes.summarizer_routes.summarize_text', {'text': 'An article.'}),
            ('/resume', 'routes.resume_routes.build_resume', {
                'name': 'Example Person', 'title': 'Teacher', 'experience': 'Two years', 'skills': 'Planning',
            }),
            ('/ppt', 'routes.ppt_routes.generate_presentation', {'topic': 'Water cycle'}),
            ('/detector', 'routes.detector_routes.detect_ai', {'text': 'A sample paragraph.'}),
        )
        for path, service, fields in cases:
            with self.subTest(path=path), patch(
                service, side_effect=GeminiGenerationError('AI is busy. Please try again.')
            ):
                response = self.client.post(
                    path, data={'_csrf_token': csrf_token(self.client), **fields}
                )
                self.assertEqual(response.status_code, 503)
                self.assertIn(
                    b'<p class="flash danger" role="alert">AI is busy. Please try again.</p>',
                    response.data,
                )
                self.assertNotIn(b'<div class="output-box">', response.data)

    def test_missing_input_is_actionable_and_never_rendered_as_output(self):
        cases = (
            ('/grammar', {'text': '  '}, 'Please paste text to fix.'),
            ('/essay', {'topic': '  '}, 'Please enter an essay topic.'),
            ('/composition', {'topic': '  '}, 'Please enter a composition topic.'),
            ('/summarizer', {'text': '  '}, 'Please paste text to summarize.'),
            ('/resume', {'name': 'Example Person'}, 'Please complete every resume field.'),
            ('/ppt', {'topic': '  '}, 'Please enter a presentation topic.'),
            ('/detector', {'text': '  '}, 'Please paste text or upload a .txt, .pdf, or .docx file to analyze.'),
        )
        for path, fields, message in cases:
            with self.subTest(path=path):
                response = self.client.post(
                    path, data={'_csrf_token': csrf_token(self.client), **fields}
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'<p class="flash danger" role="alert">', response.data)
                self.assertIn(message.encode(), response.data)
                self.assertNotIn(b'<div class="output-box">', response.data)

    def test_detector_upload_error_is_an_alert(self):
        response = self.client.post('/detector', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(b'not a document'), 'sample.exe'),
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn(b'<p class="flash danger" role="alert">', response.data)
        self.assertNotIn(b'<div class="output-box">', response.data)

    @patch('routes.grammar_routes.fix_grammar', return_value='Corrected sentence.')
    def test_success_only_uses_generated_output_box(self, _mock_service):
        response = self.client.post('/grammar', data={
            '_csrf_token': csrf_token(self.client), 'text': 'Sentence to correct.'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div class="output-box">', response.data)
        self.assertIn(b'Corrected sentence.', response.data)
        self.assertNotIn(b'<p class="flash danger" role="alert">', response.data)


if __name__ == '__main__':
    unittest.main()

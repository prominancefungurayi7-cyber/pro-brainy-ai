import json
import unittest
from io import BytesIO
from unittest.mock import patch

from docx import Document

from app import app
from models.user import UserVoiceProfile, db
from services.humanizer_service import humanize_text
from tests.helpers import csrf_token, register_client


class HumanizerQualityTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
        register_client(self.client)

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    @patch('services.humanizer_service.generate_response')
    def test_retries_changed_facts_and_selects_valid_candidate(self, mock_ai):
        mock_ai.side_effect = ['The report was finished in 3 days.',
                               'We finished the report in 2 days.']
        result = humanize_text('The report was finished in 2 days.')
        self.assertEqual(result, 'We finished the report in 2 days.')
        self.assertEqual(mock_ai.call_count, 2)

    @patch('services.humanizer_service.generate_response')
    def test_thorough_mode_compares_two_safe_candidates(self, mock_ai):
        mock_ai.side_effect = ['Furthermore, it is important to note that we finished in 2 days.',
                               'We finished in 2 days.']
        result = humanize_text('The task was finished in 2 days.', thorough=True)
        self.assertEqual(result, 'We finished in 2 days.')
        self.assertEqual(mock_ai.call_count, 2)

    @patch('services.humanizer_service.generate_response')
    def test_unchanged_first_answer_gets_one_more_rewrite_attempt(self, mock_ai):
        source = 'The task was finished in 2 days.'
        mock_ai.side_effect = [source, 'We finished the task in 2 days.']
        self.assertEqual(humanize_text(source), 'We finished the task in 2 days.')
        self.assertEqual(mock_ai.call_count, 2)

    @patch('routes.humanizer_routes.build_voice_profile')
    @patch('services.humanizer_service.generate_response', return_value='We finished in 2 days.')
    def test_saved_voice_is_used_and_can_be_deleted(self, mock_ai, mock_profile):
        mock_profile.return_value = 'Short, direct sentences with everyday words.'
        response = self.client.post('/humanizer/voice', data={
            '_csrf_token': csrf_token(self.client),
            'writing_samples': 'This is my own writing. ' * 8,
        })
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            profile = UserVoiceProfile.query.one()
            self.assertEqual(profile.style_guide, mock_profile.return_value)
            self.assertNotIn('This is my own writing', profile.style_guide)
        self.assertIn(b'Short, direct sentences', self.client.get('/humanizer').data)
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client), 'text': 'The task was finished in 2 days.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(mock_profile.return_value, mock_ai.call_args.args[0])
        self.assertEqual(self.client.post('/humanizer/voice/delete', data={
            '_csrf_token': csrf_token(self.client),
        }).status_code, 302)
        with app.app_context():
            self.assertEqual(UserVoiceProfile.query.count(), 0)

    @patch('routes.humanizer_routes.build_voice_profile', return_value='Short, direct sentences.')
    def test_saved_voice_is_private_to_its_account(self, _mock_profile):
        self.client.post('/humanizer/voice', data={
            '_csrf_token': csrf_token(self.client),
            'writing_samples': 'A paragraph I wrote myself. ' * 6,
        })
        other_client = app.test_client()
        register_client(other_client, username='Other member', email='other@example.com')
        self.assertNotIn(b'Short, direct sentences.', other_client.get('/humanizer').data)
        self.assertIn(b'Short, direct sentences.', self.client.get('/humanizer').data)

    @patch('services.humanizer_service.generate_response')
    def test_docx_retries_changed_number_and_keeps_heading(self, mock_ai):
        document = Document()
        document.add_heading('Results', level=1)
        document.add_paragraph('We finished in 2 days.')
        output = BytesIO()
        document.save(output)

        def rewrite(prompt, **_kwargs):
            source = json.loads(prompt.split('\n')[-1])
            number = '3' if mock_ai.call_count == 1 else '2'
            return json.dumps([{'id': item['id'], 'text': f'We completed it in {number} days.'}
                               for item in source])

        mock_ai.side_effect = rewrite
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(output.getvalue()), 'results.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_ai.call_count, 2)
        result = Document(BytesIO(response.data))
        self.assertEqual(result.paragraphs[0].text, 'Results')
        self.assertEqual(result.paragraphs[1].text, 'We completed it in 2 days.')

    @patch('services.humanizer_service.generate_response')
    def test_docx_retries_an_unchanged_body_paragraph(self, mock_ai):
        document = Document()
        document.add_heading('Summary', level=1)
        document.add_paragraph('The plan was discussed by the team.')
        source = BytesIO()
        document.save(source)
        mock_ai.side_effect = [
            json.dumps([{'id': 0, 'text': 'The plan was discussed by the team.'}]),
            json.dumps([{'id': 0, 'text': 'The team discussed the plan.'}]),
        ]
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client),
            'file': (BytesIO(source.getvalue()), 'summary.docx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_ai.call_count, 2)
        result = Document(BytesIO(response.data))
        self.assertEqual(result.paragraphs[0].text, 'Summary')
        self.assertEqual(result.paragraphs[1].text, 'The team discussed the plan.')


if __name__ == '__main__':
    unittest.main()

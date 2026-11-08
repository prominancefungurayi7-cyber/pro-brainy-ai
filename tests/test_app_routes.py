import unittest
from unittest.mock import patch

from app import app
from models.user import db
from tests.helpers import csrf_token, register_client


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
        register_client(self.client)
        self.client.get('/dashboard')

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_signed_in_root_opens_dashboard(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].endswith('/dashboard'))

    @patch('services.gemini_service._client', object())
    def test_health_check(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'status': 'ok', 'gemini': 'configured'})

    @patch('services.gemini_service._client', None)
    def test_health_check_reports_missing_gemini_key(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {'status': 'unavailable', 'gemini': 'missing_api_key'})

    def test_unknown_route_returns_404(self):
        response = self.client.get('/does-not-exist')
        self.assertEqual(response.status_code, 404)

    def test_tool_pages_render(self):
        routes = [
            '/humanizer',
            '/detector',
            '/grammar',
            '/essay',
            '/composition',
            '/summarizer',
            '/resume',
            '/ppt',
        ]
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)

    def test_guest_sees_account_pages_without_service_links(self):
        guest = app.test_client()
        first_visit = guest.get('/')
        self.assertEqual(first_visit.status_code, 302)
        self.assertTrue(first_visit.headers['Location'].endswith('/login'))
        for path in ('/login', '/register'):
            with self.subTest(path=path):
                response = guest.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(b'/humanizer', response.data)
                self.assertNotIn(b'Writing tools', response.data)

    def test_login_introduces_workspace_without_tool_navigation(self):
        guest = app.test_client()
        response = guest.get('/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your ideas deserve to sound like', response.data)
        self.assertIn(b'Create an account', response.data)
        self.assertIn(b'name="_csrf_token"', response.data)
        self.assertNotIn(b'/resume', response.data)

    def test_education_level_only_appears_on_school_writing_tools(self):
        without_levels = ('/humanizer', '/grammar', '/summarizer', '/resume', '/ppt', '/detector')
        for path in without_levels:
            with self.subTest(path=path):
                self.assertNotIn(b'name="education_level"', self.client.get(path).data)
        for path in ('/essay', '/composition'):
            with self.subTest(path=path):
                self.assertIn(b'name="education_level"', self.client.get(path).data)


class ServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
        register_client(self.client)

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    @patch('services.grammar_service.generate_response')
    def test_grammar_route_uses_service(self, mock_generate):
        mock_generate.return_value = 'Corrected text.'
        response = self.client.post('/grammar', data={'_csrf_token': csrf_token(self.client), 'text': 'bad grammer text'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Corrected text.', response.data)
        mock_generate.assert_called_once()

    @patch('app.record_tool_use')
    @patch('services.gemini_service._client', None)
    def test_missing_gemini_key_does_not_charge_tool_use(self, record_use):
        response = self.client.post('/grammar', data={
            '_csrf_token': csrf_token(self.client), 'text': 'Please fix this sentence.'
        })
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'temporarily unavailable', response.data)
        record_use.assert_not_called()

    @patch('services.humanizer_service.generate_response')
    def test_humanizer_route_uses_service(self, mock_generate):
        mock_generate.return_value = 'Humanized text.'
        response = self.client.post('/humanizer', data={
            '_csrf_token': csrf_token(self.client), 'text': 'robotic text',
            'voice_sample': 'I write in short, direct sentences.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Humanized text.', response.data)
        prompt = mock_generate.call_args.args[0]
        self.assertIn('I write in short, direct sentences.', prompt)
        self.assertIn('robotic text', prompt)

    @patch('services.detector_service.generate_response')
    def test_detector_route_parses_probability(self, mock_generate):
        mock_generate.return_value = '{"observations": ["Formal tone."], "alternative_explanation": "A person may write formally."}'
        response = self.client.post('/detector', data={'_csrf_token': csrf_token(self.client), 'text': 'Sample text to analyze.'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Formal tone.', response.data)

    def test_remaining_service_forms_complete_their_workflows(self):
        cases = (
            ('/essay', 'services.essay_service.generate_response', {'topic': 'Rainfall', 'word_count': '300'}),
            ('/composition', 'services.composition_service.generate_response', {'topic': 'A school event', 'word_count': '300'}),
            ('/summarizer', 'services.summarizer_service.generate_response', {'text': 'A long article.', 'style': 'concise'}),
            ('/resume', 'services.resume_service.generate_response', {
                'name': 'Example Person', 'title': 'Teacher', 'experience': 'Two years teaching', 'skills': 'Planning',
            }),
            ('/ppt', 'services.ppt_service.generate_response', {'topic': 'Water cycle', 'audience': 'Students', 'slides': '5'}),
        )
        for path, service, fields in cases:
            with self.subTest(path=path), patch(service, return_value='Workflow result.') as mock_generate:
                response = self.client.post(path, data={'_csrf_token': csrf_token(self.client), **fields})
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'Workflow result.', response.data)
                mock_generate.assert_called_once()

    def test_grammar_route_requires_text(self):
        response = self.client.post('/grammar', data={'_csrf_token': csrf_token(self.client), 'text': '   '})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please paste text to fix.', response.data)

    @patch('services.grammar_service.generate_response', return_value='Corrected text.')
    def test_free_tool_limit(self, _mock_generate):
        previous = app.config['FREE_TOOL_DAILY_LIMIT']
        app.config['FREE_TOOL_DAILY_LIMIT'] = 1
        try:
            first = self.client.post('/grammar', data={'_csrf_token': csrf_token(self.client), 'text': 'one'})
            second = self.client.post('/grammar', data={'_csrf_token': csrf_token(self.client), 'text': 'two'})
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 429)
        finally:
            app.config['FREE_TOOL_DAILY_LIMIT'] = previous


if __name__ == '__main__':
    unittest.main()

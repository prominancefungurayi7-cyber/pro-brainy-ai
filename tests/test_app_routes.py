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

    def test_homepage_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'All Your AI Writing Tools In One Place', response.data)

    def test_health_check(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'status': 'ok'})

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
        self.assertEqual(guest.get('/').status_code, 302)
        for path in ('/login', '/register'):
            with self.subTest(path=path):
                response = guest.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(b'/humanizer', response.data)
                self.assertNotIn(b'Writing tools', response.data)


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

    @patch('services.humanizer_service.generate_response')
    def test_humanizer_route_uses_service(self, mock_generate):
        mock_generate.return_value = 'Humanized text.'
        response = self.client.post('/humanizer', data={'_csrf_token': csrf_token(self.client), 'text': 'robotic text'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Humanized text.', response.data)

    @patch('services.detector_service.generate_response')
    def test_detector_route_parses_probability(self, mock_generate):
        mock_generate.return_value = '{"ai_probability": 82, "explanation": "Formal tone."}'
        response = self.client.post('/detector', data={'_csrf_token': csrf_token(self.client), 'text': 'Sample text to analyze.'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AI probability: 82%', response.data)

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

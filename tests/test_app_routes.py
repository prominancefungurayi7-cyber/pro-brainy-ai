import unittest
from unittest.mock import patch

from app import app


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

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
            '/login',
            '/register',
        ]
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)


class ServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch('services.grammar_service.generate_response')
    def test_grammar_route_uses_service(self, mock_generate):
        mock_generate.return_value = 'Corrected text.'
        response = self.client.post('/grammar', data={'text': 'bad grammer text'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Corrected text.', response.data)
        mock_generate.assert_called_once()

    @patch('services.humanizer_service.generate_response')
    def test_humanizer_route_uses_service(self, mock_generate):
        mock_generate.return_value = 'Humanized text.'
        response = self.client.post('/humanizer', data={'text': 'robotic text'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Humanized text.', response.data)

    @patch('services.detector_service.generate_response')
    def test_detector_route_parses_probability(self, mock_generate):
        mock_generate.return_value = '{"ai_probability": 82, "explanation": "Formal tone."}'
        response = self.client.post('/detector', data={'text': 'Sample text to analyze.'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AI probability: 82%', response.data)

    def test_grammar_route_requires_text(self):
        response = self.client.post('/grammar', data={'text': '   '})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please paste text to fix.', response.data)


if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import patch

from services.detector_service import detect_ai
from services.gemini_service import generate_response
from services.grammar_service import fix_grammar
from services.humanizer_service import humanize_text


class GeminiServiceTests(unittest.TestCase):
    def test_generate_response_without_api_key(self):
        with patch('services.gemini_service._client', None):
            result = generate_response('Hello')
            self.assertIn('AI service unavailable', result)

    def test_generate_response_rejects_empty_prompt(self):
        with patch('services.gemini_service._client', object()):
            result = generate_response('   ')
            self.assertIn('Please provide text', result)


class ToolServiceTests(unittest.TestCase):
    @patch('services.grammar_service.generate_response')
    def test_fix_grammar_builds_prompt(self, mock_generate):
        mock_generate.return_value = 'Fixed.'
        result = fix_grammar('broken text', 'O level')
        self.assertEqual(result, 'Fixed.')
        prompt = mock_generate.call_args[0][0]
        self.assertIn('broken text', prompt)
        self.assertIn('O level', prompt)

    @patch('services.humanizer_service.generate_response')
    def test_humanize_text_builds_prompt(self, mock_generate):
        mock_generate.return_value = 'Natural text.'
        result = humanize_text('AI text', 'Primary school')
        self.assertEqual(result, 'Natural text.')
        prompt = mock_generate.call_args[0][0]
        self.assertIn('AI text', prompt)
        self.assertIn('primary school', prompt.lower())

    @patch('services.detector_service.generate_response')
    def test_detect_ai_parses_json_probability(self, mock_generate):
        mock_generate.return_value = '{"ai_probability": 91, "explanation": "Very formal."}'
        result = detect_ai('Some text')
        self.assertIn('AI probability: 91%', result)


if __name__ == '__main__':
    unittest.main()

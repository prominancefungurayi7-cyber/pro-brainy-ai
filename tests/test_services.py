import unittest
from types import SimpleNamespace
from unittest.mock import patch

from google.genai import errors as genai_errors

from services.detector_service import detect_ai
from services.gemini_service import generate_response
from services.grammar_service import fix_grammar
from services.humanizer_service import humanize_text
from services.ppt_service import generate_presentation
from services.resume_service import build_resume
from services.summarizer_service import summarize_text


class GeminiServiceTests(unittest.TestCase):
    def test_generate_response_without_api_key(self):
        with patch('services.gemini_service._client', None):
            result = generate_response('Hello')
            self.assertIn('AI service unavailable', result)

    def test_generate_response_rejects_empty_prompt(self):
        with patch('services.gemini_service._client', object()):
            result = generate_response('   ')
            self.assertIn('Please provide text', result)

    @patch('services.gemini_service._client', object())
    @patch('services.gemini_service._generate_with_model')
    def test_rate_limit_uses_available_fallback_model(self, mock_generate):
        rate_limit = genai_errors.ClientError(429, {
            'error': {'code': 429, 'message': 'Rate limit exceeded. Retry in 20s', 'status': 'RESOURCE_EXHAUSTED'}
        })
        mock_generate.side_effect = [rate_limit, SimpleNamespace(text='Fallback response.')]
        self.assertEqual(generate_response('Hello'), 'Fallback response.')
        self.assertEqual(mock_generate.call_args_list[0].args[0], 'gemini-2.5-flash')
        self.assertEqual(mock_generate.call_args_list[1].args[0], 'gemini-3.5-flash-lite')

    @patch('services.gemini_service._client', object())
    @patch('services.gemini_service._generate_with_model')
    def test_rate_limit_on_all_models_returns_retry_guidance(self, mock_generate):
        mock_generate.side_effect = genai_errors.ClientError(429, {
            'error': {'code': 429, 'message': 'Rate limit exceeded. Retry in 20s', 'status': 'RESOURCE_EXHAUSTED'}
        })
        self.assertIn('retry in about 20 seconds', generate_response('Hello'))


class ToolServiceTests(unittest.TestCase):
    @patch('services.grammar_service.generate_response')
    def test_fix_grammar_builds_prompt(self, mock_generate):
        mock_generate.return_value = 'Fixed.'
        result = fix_grammar('broken text')
        self.assertEqual(result, 'Fixed.')
        prompt = mock_generate.call_args[0][0]
        self.assertIn('broken text', prompt)
        self.assertIn('Preserve the original meaning and tone', prompt)
        self.assertNotIn('Primary school', prompt)

    @patch('services.humanizer_service.generate_response')
    def test_humanize_text_builds_prompt(self, mock_generate):
        mock_generate.return_value = 'Natural text.'
        result = humanize_text('AI text')
        self.assertEqual(result, 'Natural text.')
        prompt = mock_generate.call_args[0][0]
        self.assertIn('AI text', prompt)
        self.assertIn('Preserve the meaning and tone', prompt)
        self.assertNotIn('primary school', prompt.lower())

    @patch('services.resume_service.generate_response', return_value='Resume draft.')
    def test_resume_prompt_is_professional_without_school_level(self, mock_generate):
        self.assertEqual(build_resume('Alex', 'Analyst', 'Three years', 'Research'), 'Resume draft.')
        prompt = mock_generate.call_args[0][0]
        self.assertIn('professional', prompt)
        self.assertNotIn('primary school', prompt.lower())

    @patch('services.summarizer_service.generate_response', return_value='Summary.')
    def test_summary_uses_style_without_school_level(self, mock_generate):
        self.assertEqual(summarize_text('Source text', 'detailed'), 'Summary.')
        prompt = mock_generate.call_args[0][0]
        self.assertIn('detailed', prompt)
        self.assertNotIn('primary school', prompt.lower())

    @patch('services.ppt_service.generate_response', return_value='Slide outline.')
    def test_presentation_uses_audience_without_school_level(self, mock_generate):
        self.assertEqual(generate_presentation('Water', 'Researchers', 5), 'Slide outline.')
        prompt = mock_generate.call_args[0][0]
        self.assertIn('Researchers', prompt)
        self.assertNotIn('primary school', prompt.lower())

    @patch('services.detector_service.generate_response')
    def test_detect_ai_parses_json_probability(self, mock_generate):
        mock_generate.return_value = '{"ai_probability": 91, "explanation": "Very formal."}'
        result = detect_ai('Some text')
        self.assertIn('AI probability: 91%', result)


if __name__ == '__main__':
    unittest.main()

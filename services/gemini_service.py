import concurrent.futures
import logging
import re
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from config import Config

api_key = (Config.GEMINI_API_KEY or '').strip()
DEFAULT_MODEL = 'gemini-2.5-flash'
FALLBACK_MODELS = ['gemini-2.0-flash', 'gemini-flash-latest']
MODELS = [DEFAULT_MODEL] + FALLBACK_MODELS
TIMEOUT_SECONDS = 45

_client = None
if api_key:
    _client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000),
    )
elif not Config.TESTING:
    logging.getLogger(__name__).error(
        'GEMINI_API_KEY is missing from this process; all AI tools are unavailable. '
        'Set it on the running service and deploy the change.'
    )


def is_gemini_configured():
    """Report whether this process can make Gemini requests without exposing its key."""
    return _client is not None


class GeminiGenerationError(RuntimeError):
    """A user-safe error for callers that need to reject invalid AI output."""


def _failure(message, raise_on_error):
    if raise_on_error:
        raise GeminiGenerationError(message)
    return message


def _extract_text_from_response(response):
    if response is None:
        return None
    if hasattr(response, 'text') and response.text:
        return response.text
    if hasattr(response, 'candidates') and response.candidates:
        candidate = response.candidates[0]
        content = getattr(candidate, 'content', None)
        if content and hasattr(content, 'parts') and content.parts:
            text_parts = []
            for part in content.parts:
                part_text = getattr(part, 'text', None)
                if part_text:
                    text_parts.append(part_text)
            if text_parts:
                return ''.join(text_parts)
        return getattr(candidate, 'output', str(candidate))
    return str(response)


def _parse_retry_seconds(exc_text):
    if not exc_text:
        return None
    match = re.search(r'retry in\s*(\d+(?:\.\d+)?)s', exc_text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    match = re.search(r'Retry-After:\s*(\d+)', exc_text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _is_rate_limit_error(error_text):
    lowered = error_text.lower()
    return (
        'quota' in lowered
        or '429' in error_text
        or 'rate limit' in lowered
        or 'resource_exhausted' in lowered
    )


def _generate_with_model(model_name, prompt, config=None):
    options = {'model': model_name, 'contents': prompt}
    if config is not None:
        options['config'] = config
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(
            _client.models.generate_content,
            **options,
        )
        try:
            return future.result(timeout=TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f'AI generation timed out after {TIMEOUT_SECONDS} seconds. Try again later.'
            ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def generate_response(prompt, *, config=None, raise_on_error=False):
    if not _client:
        return _failure('AI service unavailable. Please try again later.', raise_on_error)

    if not prompt or not str(prompt).strip():
        return _failure('Please provide text for the AI to process.', raise_on_error)

    last_error = None
    for candidate_model in MODELS:
        try:
            response = _generate_with_model(candidate_model, prompt, config=config)
            text = _extract_text_from_response(response)
            if text:
                return text
            last_error = RuntimeError(f'Model {candidate_model} returned an empty response.')
        except TimeoutError as error:
            return _failure(str(error), raise_on_error)
        except genai_errors.ClientError as error:
            last_error = error
            error_text = str(error)
            if _is_rate_limit_error(error_text):
                retry_seconds = _parse_retry_seconds(error_text)
                if retry_seconds:
                    return _failure((
                        f'Quota exceeded for model {candidate_model}. '
                        f'Please retry in {int(retry_seconds)} seconds or check billing/limits.'
                    ), raise_on_error)
                return _failure((
                    f'Quota or rate-limit exceeded for model {candidate_model}. '
                    'Check your plan and billing details.'
                ), raise_on_error)
        except genai_errors.ServerError as error:
            last_error = error
            error_text = str(error)
            if _is_rate_limit_error(error_text):
                retry_seconds = _parse_retry_seconds(error_text)
                if retry_seconds:
                    return _failure((
                        f'Service busy for model {candidate_model}. '
                        f'Please retry in {int(retry_seconds)} seconds.'
                    ), raise_on_error)
            continue
        except Exception as error:
            last_error = error
            error_text = str(error)
            if _is_rate_limit_error(error_text):
                retry_seconds = _parse_retry_seconds(error_text)
                if retry_seconds:
                    return _failure((
                        f'Quota exceeded for model {candidate_model}. '
                        f'Please retry in {int(retry_seconds)} seconds or check billing/limits.'
                    ), raise_on_error)
                return _failure((
                    f'Quota or rate-limit exceeded for model {candidate_model}. '
                    'Check your plan and billing details.'
                ), raise_on_error)
            continue

    if last_error:
        logging.getLogger(__name__).warning('Gemini request failed: %s', type(last_error).__name__)
        return _failure('AI service temporarily unavailable. Please try again.', raise_on_error)
    return _failure('Error generating AI content: unknown error', raise_on_error)

import google.generativeai as genai
from config import Config
import concurrent.futures
import re
import time

api_key = Config.GEMINI_API_KEY
DEFAULT_MODEL = 'gemini-flash-latest'
FALLBACK_MODELS = ['gemini-2.5-flash', 'gemini-2.0-flash']
MODELS = [DEFAULT_MODEL] + FALLBACK_MODELS
TIMEOUT_SECONDS = 20

genai_configured = False
if api_key:
    genai.configure(api_key=api_key)
    genai_configured = True


def _extract_text_from_response(response):
    if hasattr(response, 'text') and response.text:
        return response.text
    if hasattr(response, 'candidates') and response.candidates:
        candidate = response.candidates[0]
        return getattr(candidate, 'output', getattr(candidate, 'content', str(candidate)))
    if hasattr(response, 'content'):
        return response.content
    return str(response)


def _parse_retry_seconds(exc_text):
    # Look for patterns like 'retry in 24.5s' or 'Retry-After: 24'
    if not exc_text:
        return None
    m = re.search(r'retry in\s*(\d+(?:\.\d+)?)s', exc_text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    m2 = re.search(r'Retry-After:\s*(\d+)', exc_text, re.IGNORECASE)
    if m2:
        try:
            return int(m2.group(1))
        except Exception:
            return None
    return None


def generate_response(prompt):
    if not genai_configured:
        return 'AI service unavailable. Configure GEMINI_API_KEY and restart the app.'

    last_error = None
    # Try each model in order; if one returns a quota/429 error, try the next
    for candidate_model in MODELS:
        try:
            try:
                model = genai.GenerativeModel(candidate_model)
            except Exception as e:
                last_error = e
                continue

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(model.generate_content, prompt)
                try:
                    response = fut.result(timeout=TIMEOUT_SECONDS)
                except concurrent.futures.TimeoutError:
                    return f'AI generation timed out after {TIMEOUT_SECONDS} seconds. Try again later.'

            return _extract_text_from_response(response)

        except Exception as error:
            last_error = error
            text = str(error)
            # Detect quota / rate limit messages with 429 and suggested retry
            if 'quota' in text.lower() or '429' in text or 'rate limit' in text.lower():
                retry_seconds = _parse_retry_seconds(text)
                if retry_seconds:
                    # Surface a clear message to the user with retry time
                    return f'Quota exceeded for model {candidate_model}. Please retry in {int(retry_seconds)} seconds or check billing/limits.'
                else:
                    return f'Quota or rate-limit exceeded for model {candidate_model}. Check your plan and billing details.'
            # otherwise try next candidate_model
            continue

    # If we exhausted models
    if last_error:
        return f'Error generating AI content: {last_error}'
    return 'Error generating AI content: unknown error'

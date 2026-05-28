from services.gemini_service import generate_response
from services.level_service import build_level_instruction


def summarize_text(text, style='concise', education_level='Primary school'):
    prompt = f"""
Summarize the following text in a {style} style.
{build_level_instruction(education_level)}
Keep the key ideas and remove any repetition.

TEXT:
{text}
"""
    return generate_response(prompt)

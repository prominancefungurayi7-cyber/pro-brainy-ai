from services.gemini_service import generate_response


def summarize_text(text, style='concise'):
    prompt = f"""
Summarize the following text in a {style} style.
Keep the key ideas and facts, remove repetition, and match the source's level of formality.

TEXT:
{text}
"""
    return generate_response(prompt)

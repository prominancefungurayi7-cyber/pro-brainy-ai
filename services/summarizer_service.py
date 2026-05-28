from services.gemini_service import generate_response

def summarize_text(text, style='concise'):
    prompt = f"""
Summarize the following text in a {style} style.
Keep the key ideas and remove any repetition.

TEXT:
{text}
"""
    return generate_response(prompt)

from services.gemini_service import generate_response


def humanize_text(text):
    prompt = f'''
    Rewrite the following text naturally in a human voice.
    Return only the rewritten text with no commentary, labels, or explanations.
    Preserve the meaning and tone, but make the wording flow naturally.

    TEXT:
    {text}
    '''

    return generate_response(prompt)

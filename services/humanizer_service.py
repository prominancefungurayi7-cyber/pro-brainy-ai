from services.gemini_service import generate_response
from services.level_service import build_level_instruction


def humanize_text(text, education_level='Primary school'):
    prompt = f'''
    Rewrite the following text naturally in a human voice.
    {build_level_instruction(education_level)}
    Return only the rewritten text with no commentary, labels, or explanations.
    Preserve the meaning and tone, but make the wording flow naturally.

    TEXT:
    {text}
    '''

    return generate_response(prompt)

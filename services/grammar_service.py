from services.gemini_service import generate_response



def fix_grammar(text):
    prompt = f'''
    Correct grammar and improve readability.
    Preserve the original meaning and tone. Return only the corrected text.

    TEXT:
    {text}
    '''

    return generate_response(prompt)

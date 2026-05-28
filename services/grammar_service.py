from services.gemini_service import generate_response



def fix_grammar(text):
    prompt = f'''
    Correct grammar and improve readability.
    Do not change the original meaning.

    TEXT:
    {text}
    '''

    return generate_response(prompt)
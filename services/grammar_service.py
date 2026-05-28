from services.gemini_service import generate_response
from services.level_service import build_level_instruction



def fix_grammar(text, education_level='Primary school'):
    prompt = f'''
    Correct grammar and improve readability.
    {build_level_instruction(education_level)}
    Do not change the original meaning.

    TEXT:
    {text}
    '''

    return generate_response(prompt)
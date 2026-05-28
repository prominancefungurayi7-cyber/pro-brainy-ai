from services.gemini_service import generate_response
from services.level_service import build_level_instruction


def generate_composition(topic, word_count=300, education_level='Primary school'):
    prompt = f"""
Write a composition on the following topic:
"{topic}"

{build_level_instruction(education_level)}
Use a clear beginning, middle, and ending. Include interesting details and smooth transitions.
Aim for approximately {word_count} words.

Composition:
"""
    return generate_response(prompt)

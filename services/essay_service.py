from services.gemini_service import generate_response

def generate_essay(topic, word_count=500):
    prompt = f"""
Write a well-organized essay about \"{topic}\".
Use clear paragraphs and natural language.
Aim for approximately {word_count} words.

Essay:
"""
    return generate_response(prompt)

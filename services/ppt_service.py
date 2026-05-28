from services.gemini_service import generate_response
from services.level_service import build_level_instruction


def generate_presentation(topic, audience, slide_count=5, education_level='Primary school'):
    audience_text = f'for {audience}' if audience else ''
    prompt = f"""
Create a {slide_count}-slide presentation outline about \"{topic}\" {audience_text}.
{build_level_instruction(education_level)}
List slide titles and a short bullet summary for each slide.
"""
    return generate_response(prompt)

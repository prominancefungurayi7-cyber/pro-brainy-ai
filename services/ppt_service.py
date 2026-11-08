from services.gemini_service import generate_response


def generate_presentation(topic, audience, slide_count=5):
    audience_text = f'for {audience}' if audience else ''
    prompt = f"""
Create a {slide_count}-slide presentation outline about \"{topic}\" {audience_text}.
Match the language and detail to the stated audience. List slide titles and a short
bullet summary for each slide. Do not add unsupported facts.
"""
    return generate_response(prompt)

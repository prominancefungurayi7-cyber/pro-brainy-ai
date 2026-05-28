from services.gemini_service import generate_response

def generate_presentation(topic, audience, slide_count=5):
    audience_text = f'for {audience}' if audience else ''
    prompt = f"""
Create a {slide_count}-slide presentation outline about \"{topic}\" {audience_text}.
List slide titles and a short bullet summary for each slide.
"""
    return generate_response(prompt)

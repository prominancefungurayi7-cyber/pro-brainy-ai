from services.gemini_service import generate_response
import re


def detect_ai(text):
    prompt = f'''
    Analyze the following text and return results in JSON format.
    Include the fields:
    - ai_probability: number between 0 and 100
    - explanation: short reason for the score

    TEXT:
    {text}
    '''

    response = generate_response(prompt)
    if not response:
        return 'AI detector did not return a result.'

    match = re.search(r'(\d{1,3})\s*%', response)
    if match:
        probability = int(match.group(1))
        explanation = response.strip()
        return f'AI probability: {probability}%\n\n{explanation}'

    match = re.search(r'"ai_probability"\s*[:=]\s*(\d{1,3})', response)
    if match:
        probability = int(match.group(1))
        explanation = response.strip()
        return f'AI probability: {probability}%\n\n{explanation}'

    return f'Could not parse AI probability percentage.\n\n{response}'

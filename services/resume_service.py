from services.gemini_service import generate_response
from services.level_service import build_level_instruction


def build_resume(name, title, experience, skills, education_level='Primary school'):
    prompt = f"""
Create a professional resume summary and experience outline for the following candidate:

Name: {name}
Title: {title}
Experience: {experience}
Skills: {skills}

{build_level_instruction(education_level)}
Provide a polished resume-ready version.
"""
    return generate_response(prompt)

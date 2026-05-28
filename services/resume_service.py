from services.gemini_service import generate_response

def build_resume(name, title, experience, skills):
    prompt = f"""
Create a professional resume summary and experience outline for the following candidate:

Name: {name}
Title: {title}
Experience: {experience}
Skills: {skills}

Provide a polished resume-ready version.
"""
    return generate_response(prompt)

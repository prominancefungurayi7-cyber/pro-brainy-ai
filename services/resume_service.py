from services.gemini_service import generate_response


def build_resume(name, title, experience, skills):
    prompt = f"""
Create a professional resume summary and experience outline for the following candidate:

Name: {name}
Title: {title}
Experience: {experience}
Skills: {skills}

Provide a polished, professional resume-ready version. Use only the supplied facts;
do not invent employers, qualifications, dates, or achievements.
"""
    return generate_response(prompt)

from flask import Blueprint, g, render_template, request
from services.gemini_service import GeminiGenerationError
from services.resume_service import build_resume

resume_bp = Blueprint('resume', __name__)

@resume_bp.route('/resume', methods=['GET', 'POST'])
def resume_generator():
    output = None
    error = None
    status = 200
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        title = (request.form.get('title') or '').strip()
        experience = (request.form.get('experience') or '').strip()
        skills = (request.form.get('skills') or '').strip()
        if name and title and experience and skills:
            try:
                output = build_resume(name, title, experience, skills)
                g.tool_generated = True
            except GeminiGenerationError as exc:
                error, status = str(exc), 503
        else:
            error = 'Please complete every resume field.'

    return render_template('tools/resume_generator.html', output=output, error=error), status

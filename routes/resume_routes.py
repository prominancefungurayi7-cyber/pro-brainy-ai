from flask import Blueprint, render_template, request
from services.resume_service import build_resume

resume_bp = Blueprint('resume', __name__)

@resume_bp.route('/resume', methods=['GET', 'POST'])
def resume_generator():
    output = None
    if request.method == 'POST':
        name = request.form.get('name')
        title = request.form.get('title')
        experience = request.form.get('experience')
        skills = request.form.get('skills')
        education_level = request.form.get('education_level', 'Primary school')

        if name and title and experience and skills:
            output = build_resume(name, title, experience, skills, education_level)

    return render_template('tools/resume_generator.html', output=output)

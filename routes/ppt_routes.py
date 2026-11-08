from flask import Blueprint, g, render_template, request
from services.gemini_service import GeminiGenerationError
from services.ppt_service import generate_presentation

ppt_bp = Blueprint('ppt', __name__)

@ppt_bp.route('/ppt', methods=['GET', 'POST'])
def ppt_generator():
    output = None
    error = None
    status = 200
    if request.method == 'POST':
        topic = (request.form.get('topic') or '').strip()
        audience = request.form.get('audience')
        slides = request.form.get('slides', 5)
        try:
            slides = max(3, min(20, int(slides)))
        except (ValueError, TypeError):
            slides = 5

        if topic:
            try:
                output = generate_presentation(topic, audience, slides)
                g.tool_generated = True
            except GeminiGenerationError as exc:
                error, status = str(exc), 503
        else:
            error = 'Please enter a presentation topic.'

    return render_template('tools/ppt_generator.html', output=output, error=error), status

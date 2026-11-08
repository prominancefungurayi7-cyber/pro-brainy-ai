from flask import Blueprint, g, render_template, request
from services.gemini_service import GeminiGenerationError
from services.composition_service import generate_composition

composition_bp = Blueprint('composition', __name__)


@composition_bp.route('/composition', methods=['GET', 'POST'])
def composition_writer():
    output = None
    error = None
    status = 200
    if request.method == 'POST':
        topic = (request.form.get('topic') or '').strip()
        word_count = request.form.get('word_count', 300)
        education_level = request.form.get('education_level', 'Primary school')

        try:
            word_count = max(100, min(2000, int(word_count)))
        except (ValueError, TypeError):
            word_count = 300

        if topic:
            try:
                output = generate_composition(topic, word_count, education_level)
                g.tool_generated = True
            except GeminiGenerationError as exc:
                error, status = str(exc), 503
        else:
            error = 'Please enter a composition topic.'

    return render_template('tools/composition_writer.html', output=output, error=error), status

from flask import Blueprint, g, render_template, request
from services.gemini_service import GeminiGenerationError
from services.essay_service import generate_essay

essay_bp = Blueprint('essay', __name__)

@essay_bp.route('/essay', methods=['GET', 'POST'])
def essay_generator():
    output = None
    error = None
    status = 200
    if request.method == 'POST':
        topic = (request.form.get('topic') or '').strip()
        word_count = request.form.get('word_count', 500)
        education_level = request.form.get('education_level', 'Primary school')
        try:
            word_count = max(100, min(2000, int(word_count)))
        except (ValueError, TypeError):
            word_count = 500

        if topic:
            try:
                output = generate_essay(topic, word_count, education_level)
                g.tool_generated = True
            except GeminiGenerationError as exc:
                error, status = str(exc), 503
        else:
            error = 'Please enter an essay topic.'

    return render_template('tools/essay_generator.html', output=output, error=error), status

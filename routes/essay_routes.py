from flask import Blueprint, render_template, request
from services.essay_service import generate_essay

essay_bp = Blueprint('essay', __name__)

@essay_bp.route('/essay', methods=['GET', 'POST'])
def essay_generator():
    output = None
    if request.method == 'POST':
        topic = request.form.get('topic')
        word_count = request.form.get('word_count', 500)
        try:
            word_count = int(word_count)
        except (ValueError, TypeError):
            word_count = 500

        if topic:
            output = generate_essay(topic, word_count)

    return render_template('tools/essay_generator.html', output=output)

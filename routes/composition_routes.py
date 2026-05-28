from flask import Blueprint, render_template, request
from services.composition_service import generate_composition

composition_bp = Blueprint('composition', __name__)


@composition_bp.route('/composition', methods=['GET', 'POST'])
def composition_writer():
    output = None
    if request.method == 'POST':
        topic = request.form.get('topic')
        word_count = request.form.get('word_count', 300)
        education_level = request.form.get('education_level', 'Primary school')

        try:
            word_count = int(word_count)
        except (ValueError, TypeError):
            word_count = 300

        if topic:
            output = generate_composition(topic, word_count, education_level)

    return render_template('tools/composition_writer.html', output=output)

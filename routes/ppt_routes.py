from flask import Blueprint, render_template, request
from services.ppt_service import generate_presentation

ppt_bp = Blueprint('ppt', __name__)

@ppt_bp.route('/ppt', methods=['GET', 'POST'])
def ppt_generator():
    output = None
    if request.method == 'POST':
        topic = request.form.get('topic')
        audience = request.form.get('audience')
        slides = request.form.get('slides', 5)
        try:
            slides = int(slides)
        except (ValueError, TypeError):
            slides = 5

        if topic:
            output = generate_presentation(topic, audience, slides)

    return render_template('tools/ppt_generator.html', output=output)

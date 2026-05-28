from flask import Blueprint, render_template, request
from services.summarizer_service import summarize_text

summarizer_bp = Blueprint('summarizer', __name__)

@summarizer_bp.route('/summarizer', methods=['GET', 'POST'])
def summarizer():
    output = None
    if request.method == 'POST':
        text = request.form.get('text')
        style = request.form.get('style', 'concise')
        education_level = request.form.get('education_level', 'Primary school')

        if text:
            output = summarize_text(text, style, education_level)

    return render_template('tools/summarizer.html', output=output)

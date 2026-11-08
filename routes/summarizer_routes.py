from flask import Blueprint, g, render_template, request
from services.gemini_service import GeminiGenerationError
from services.summarizer_service import summarize_text

summarizer_bp = Blueprint('summarizer', __name__)

@summarizer_bp.route('/summarizer', methods=['GET', 'POST'])
def summarizer():
    output = None
    error = None
    status = 200
    if request.method == 'POST':
        text = (request.form.get('text') or '').strip()
        style = request.form.get('style', 'concise')
        if text:
            try:
                output = summarize_text(text, style)
                g.tool_generated = True
            except GeminiGenerationError as exc:
                error, status = str(exc), 503
        else:
            error = 'Please paste text to summarize.'

    return render_template('tools/summarizer.html', output=output, error=error), status

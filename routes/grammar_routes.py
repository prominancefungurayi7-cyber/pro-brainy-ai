from flask import Blueprint, g, render_template, request
from services.gemini_service import GeminiGenerationError
from services.grammar_service import fix_grammar


grammar_bp = Blueprint('grammar', __name__)


@grammar_bp.route('/grammar', methods=['GET', 'POST'])
def grammar():
    output = None
    error = None
    status = 200

    if request.method == 'POST':
        user_text = (request.form.get('text') or '').strip()
        if user_text:
            try:
                output = fix_grammar(user_text)
                g.tool_generated = True
            except GeminiGenerationError as exc:
                error, status = str(exc), 503
        else:
            error = 'Please paste text to fix.'

    return render_template('tools/grammar.html', output=output, error=error), status

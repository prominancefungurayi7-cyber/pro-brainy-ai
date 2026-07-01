from flask import Blueprint, render_template, request
from services.grammar_service import fix_grammar


grammar_bp = Blueprint('grammar', __name__)


@grammar_bp.route('/grammar', methods=['GET', 'POST'])
def grammar():
    output = None

    if request.method == 'POST':
        user_text = (request.form.get('text') or '').strip()
        education_level = request.form.get('education_level', 'Primary school')

        if user_text:
            output = fix_grammar(user_text, education_level)
        else:
            output = 'Please paste text to fix.'

    return render_template('tools/grammar.html', output=output)
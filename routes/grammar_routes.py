from flask import Blueprint, render_template, request
from services.grammar_service import fix_grammar


grammar_bp = Blueprint('grammar', __name__)


@grammar_bp.route('/grammar', methods=['GET', 'POST'])
def grammar():
    output = None

    if request.method == 'POST':
        user_text = request.form.get('text')
        education_level = request.form.get('education_level', 'Primary school')
        output = fix_grammar(user_text, education_level)

    return render_template('tools/grammar.html', output=output)
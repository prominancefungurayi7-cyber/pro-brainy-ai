from flask import Blueprint, render_template, request
from services.grammar_service import fix_grammar


grammar_bp = Blueprint('grammar', __name__)


@grammar_bp.route('/grammar', methods=['GET', 'POST'])
def grammar():
    output = None

    if request.method == 'POST':
        user_text = request.form.get('text')
        output = fix_grammar(user_text)

    return render_template('tools/grammar.html', output=output)
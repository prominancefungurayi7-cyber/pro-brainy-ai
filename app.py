import os
import hmac
import secrets

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user

from config import Config
from models.user import User, db
from services.auth_security import record_tool_use, tool_limit_reached
from services.gemini_service import is_gemini_configured

app = Flask(__name__)
app.config.from_object(Config)

PROTECTED_BLUEPRINTS = {
    'humanizer', 'detector', 'grammar', 'essay', 'composition',
    'summarizer', 'resume', 'ppt',
}

if (
    not app.config['DEBUG']
    and not app.config['TESTING']
    and app.config['SECRET_KEY'] == 'dev-only-change-me-before-production'
):
    raise RuntimeError(
        'Set a strong SECRET_KEY environment variable before running in production.'
    )

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)


@app.context_processor
def inject_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_urlsafe(32)
    return {'csrf_token': session['_csrf_token']}


@app.before_request
def protect_tools_and_forms():
    if request.blueprint in PROTECTED_BLUEPRINTS and not current_user.is_authenticated:
        return login_manager.unauthorized()
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        expected = session.get('_csrf_token', '')
        supplied = request.form.get('_csrf_token', '') or request.headers.get('X-CSRF-Token', '')
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            abort(400, description='Invalid form token. Refresh the page and try again.')
    if request.blueprint in PROTECTED_BLUEPRINTS and request.method == 'POST':
        if request.endpoint not in {'humanizer.humanizer_download', 'humanizer.delete_voice'}:
            if not is_gemini_configured():
                abort(503, description='AI tools are temporarily unavailable.')
            if tool_limit_reached(current_user.id):
                abort(429, description='Tool limit reached. Please try again later.')
            record_tool_use(current_user.id)


@login_manager.user_loader
def load_user(user_id):
    if user_id is None:
        return None
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


from routes.auth_routes import auth_bp
from routes.composition_routes import composition_bp
from routes.dashboard_routes import dashboard_bp
from routes.detector_routes import detector_bp
from routes.essay_routes import essay_bp
from routes.grammar_routes import grammar_bp
from routes.humanizer_routes import humanizer_bp
from routes.ppt_routes import ppt_bp
from routes.resume_routes import resume_bp
from routes.summarizer_routes import summarizer_bp

app.register_blueprint(humanizer_bp)
app.register_blueprint(detector_bp)
app.register_blueprint(grammar_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(essay_bp)
app.register_blueprint(summarizer_bp)
app.register_blueprint(resume_bp)
app.register_blueprint(ppt_bp)
app.register_blueprint(composition_bp)


with app.app_context():
    db.create_all()


@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return redirect(url_for('auth.login'))


@app.route('/health')
def health():
    if not is_gemini_configured():
        return jsonify({'status': 'unavailable', 'gemini': 'missing_api_key'}), 503
    return jsonify({'status': 'ok', 'gemini': 'configured'}), 200


@app.errorhandler(404)
def page_not_found(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500


@app.errorhandler(503)
def service_unavailable(error):
    return render_template('errors/503.html'), 503


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])

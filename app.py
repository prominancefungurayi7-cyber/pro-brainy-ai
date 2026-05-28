from flask import Flask, render_template
from flask_login import LoginManager
from config import Config
from models.user import db, User

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    if user_id is None:
        return None
    return User.query.get(int(user_id))

# Import routes after app initialization
from routes.humanizer_routes import humanizer_bp
from routes.detector_routes import detector_bp
from routes.grammar_routes import grammar_bp
from routes.auth_routes import auth_bp
from routes.dashboard_routes import dashboard_bp
from routes.essay_routes import essay_bp
from routes.summarizer_routes import summarizer_bp
from routes.resume_routes import resume_bp
from routes.ppt_routes import ppt_bp
from routes.composition_routes import composition_bp

# Register blueprints
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


@app.before_request
def ensure_database_tables():
    with app.app_context():
        db.create_all()


@app.route('/')
def home():
    return render_template('index.html')


@app.errorhandler(404)
def page_not_found(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)
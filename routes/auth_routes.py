from flask import Blueprint, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from models.user import User, db
from services.auth_security import (
    clear_login_attempts, issue_device_cookie, known_device_token,
    record_failed_login, record_signup, signup_allowed, too_many_login_attempts,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        if not email or not password:
            flash('Email and password are required.', 'danger')
            return redirect(url_for('auth.login'))
        if too_many_login_attempts(email):
            flash('Too many login attempts. Please try again in 15 minutes.', 'danger')
            return render_template('auth/login.html'), 429
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            clear_login_attempts(email)
            session.clear()
            session.permanent = True
            login_user(user, remember=True)
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard.dashboard'))
        record_failed_login(email)
        flash('Invalid login credentials. Please try again.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    if request.method == 'GET':
        response = make_response(render_template('auth/register.html'))
        if not known_device_token():
            issue_device_cookie(response)
        return response
    username = (request.form.get('username') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    if not username or not email or not password:
        flash('Username, email, and password are required.', 'danger')
        return redirect(url_for('auth.register'))
    if len(password) < 12:
        flash('Password must be at least 12 characters long.', 'danger')
        return redirect(url_for('auth.register'))
    if len(username) > 100 or len(email) > 150 or len(password) > 1024 or '@' not in email:
        flash('Please check your account details and try again.', 'danger')
        return redirect(url_for('auth.register'))
    token = known_device_token()
    if not token or not signup_allowed(token, username):
        flash('Registration limit reached. Please use an existing account or contact support.', 'danger')
        return redirect(url_for('auth.register'))
    if User.query.filter_by(email=email).first():
        flash('Please use an existing account or a different email address.', 'warning')
        return redirect(url_for('auth.register'))
    user = User(username=username, email=email, password=generate_password_hash(password))
    db.session.add(user)
    db.session.flush()
    record_signup(user, token)
    session.clear()
    session.permanent = True
    login_user(user, remember=True)
    flash('Account created successfully.', 'success')
    return redirect(url_for('dashboard.dashboard'))


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

import hashlib
import hmac
import ipaddress
import os
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from threading import Lock

from flask import current_app, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from models.user import AuthAttempt, SignupSignal, db


DEVICE_COOKIE = 'pro_brainy_device'
DEVICE_MAX_AGE = 365 * 24 * 60 * 60
_tool_reservation_lock = Lock()


def _client_ip():
    """Use Render's normalized client address only on a Render service."""
    if os.getenv('RENDER', '').lower() == 'true':
        forwarded = request.headers.get('X-Forwarded-For', '').split(',', 1)[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return request.remote_addr or 'unknown'


def _hash(value):
    secret = current_app.config['SECRET_KEY'].encode('utf-8')
    return hmac.new(secret, value.encode('utf-8'), hashlib.sha256).hexdigest()


def _device_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='signup-device-v1')


def known_device_token():
    signed = request.cookies.get(DEVICE_COOKIE, '')
    try:
        token = _device_serializer().loads(signed, max_age=DEVICE_MAX_AGE)
    except BadSignature:
        return None
    return token if isinstance(token, str) and len(token) >= 32 else None


def issue_device_cookie(response, token=None):
    token = token or secrets.token_urlsafe(32)
    response.set_cookie(
        DEVICE_COOKIE,
        _device_serializer().dumps(token),
        max_age=DEVICE_MAX_AGE,
        httponly=True,
        secure=current_app.config['SESSION_COOKIE_SECURE'],
        samesite='Lax',
    )
    return response


def device_hash(token):
    return _hash('device:' + token)


def name_key(name):
    normalized = ' '.join(unicodedata.normalize('NFKC', name).casefold().split())
    return _hash('name:' + normalized)


def _recent_count(scope, key, minutes):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return AuthAttempt.query.filter(
        AuthAttempt.scope == scope,
        AuthAttempt.key_hash == _hash(key),
        AuthAttempt.created_at >= cutoff,
    ).count()


def _prune_attempts():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=25)
    AuthAttempt.query.filter(AuthAttempt.created_at < cutoff).delete()


def too_many_login_attempts(email):
    return (
        _recent_count('login_email', 'email:' + email, 15) >= 5
        or _recent_count('login_ip', 'ip:' + _client_ip(), 15) >= 30
    )


def record_failed_login(email):
    _prune_attempts()
    db.session.add(AuthAttempt(scope='login_email', key_hash=_hash('email:' + email)))
    db.session.add(AuthAttempt(scope='login_ip', key_hash=_hash('ip:' + _client_ip())))
    db.session.commit()


def clear_login_attempts(email):
    AuthAttempt.query.filter_by(scope='login_email', key_hash=_hash('email:' + email)).delete()
    db.session.commit()


def signup_allowed(token, username):
    hashed = device_hash(token)
    if SignupSignal.query.filter_by(device_hash=hashed).count() >= 3:
        return False
    if SignupSignal.query.filter_by(device_hash=hashed, name_key=name_key(username)).first():
        return False
    return _recent_count('signup_ip', 'ip:' + _client_ip(), 60) < 20


def record_signup(user, token):
    _prune_attempts()
    normalized_name = name_key(user.username)
    db.session.add(SignupSignal(
        user_id=user.id,
        device_hash=device_hash(token),
        name_key=normalized_name,
        duplicate_name_seen=SignupSignal.query.filter_by(name_key=normalized_name).first() is not None,
    ))
    db.session.add(AuthAttempt(scope='signup_ip', key_hash=_hash('ip:' + _client_ip())))
    db.session.commit()


def tool_limit_reached(user_id):
    key = 'user:' + str(user_id)
    daily_limit = current_app.config.get('FREE_TOOL_DAILY_LIMIT', 30)
    return _recent_count('tool', key, 1) >= 5 or _recent_count('tool', key, 24 * 60) >= daily_limit


def reserve_tool_use(user_id):
    """Reserve capacity before generation; cap failed API attempts as well."""
    key = 'user:' + str(user_id)
    with _tool_reservation_lock:
        if tool_limit_reached(user_id):
            return None
        if _recent_count('tool_attempt', key, 60) >= 15:
            return None
        if _recent_count('tool_attempt', key, 24 * 60) >= 90:
            return None
        _prune_attempts()
        db.session.add(AuthAttempt(scope='tool_attempt', key_hash=_hash(key)))
        reservation = AuthAttempt(scope='tool', key_hash=_hash(key))
        db.session.add(reservation)
        db.session.commit()
        return reservation.id


def refund_tool_reservation(reservation_id):
    reservation = db.session.get(AuthAttempt, reservation_id)
    if reservation is not None and reservation.scope == 'tool':
        db.session.delete(reservation)
        db.session.commit()

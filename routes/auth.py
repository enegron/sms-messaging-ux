"""Authentication utilities."""

from functools import wraps
from datetime import datetime, timezone

from flask import session, redirect, url_for, request, jsonify

# Session expires after 4 hours (in seconds)
SESSION_EXPIRY_SECONDS = 4 * 60 * 60


def is_session_expired():
    """Check if the current session has expired.

    Returns:
        bool: True if session is expired or login_time not set.
    """
    login_time = session.get('login_time')
    if not login_time:
        return True

    # login_time is stored as ISO format string
    login_dt = datetime.fromisoformat(login_time)
    now = datetime.now(timezone.utc)
    elapsed = (now - login_dt).total_seconds()

    return elapsed > SESSION_EXPIRY_SECONDS


def login_required(f):
    """Decorator to require operator authentication.

    Checks both that operator is logged in and that session hasn't expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'operator_id' not in session or is_session_expired():
            # Clear expired session
            session.clear()
            if request.is_json:
                return jsonify({'error': 'unauthorized', 'message': 'Authentication required'}), 401
            return redirect(url_for('dashboard.login'))
        return f(*args, **kwargs)
    return decorated_function

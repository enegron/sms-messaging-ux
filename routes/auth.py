"""Authentication utilities."""

from functools import wraps

from flask import session, redirect, url_for, request, jsonify


def login_required(f):
    """Decorator to require operator authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'operator_id' not in session:
            if request.is_json:
                return jsonify({'error': 'unauthorized', 'message': 'Authentication required'}), 401
            return redirect(url_for('dashboard.login'))
        return f(*args, **kwargs)
    return decorated_function

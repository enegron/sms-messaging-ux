"""Dashboard routes."""

import logging
from datetime import datetime, timezone
import os

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, current_app
from werkzeug.security import check_password_hash

from services.firebase import get_db, get_operator_password_hash
from routes.auth import login_required

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page for operators.

    Validates password against hashed password stored in Firestore.
    Creates session with login timestamp for 4-hour expiration.
    """
    if request.method == 'POST':
        password = request.form.get('password', '')

        # Get hashed password from Firestore
        password_hash = get_operator_password_hash()

        if password_hash is None:
            logger.error("No operator password configured in Firestore")
            return render_template('login.html', error="System not configured. Please contact administrator.")

        if check_password_hash(password_hash, password):
            session['operator_id'] = 'operator_default'
            session['operator_name'] = 'Operator'
            session['login_time'] = datetime.now(timezone.utc).isoformat()
            logger.info("Operator logged in")
            return redirect(url_for('dashboard.index'))
        else:
            logger.warning("Failed login attempt")
            return render_template('login.html', error="Invalid password")

    return render_template('login.html', error=None)


@dashboard_bp.route('/logout')
def logout():
    """Log out operator."""
    session.clear()
    return redirect(url_for('dashboard.login'))


@dashboard_bp.route('/health')
def health():
    """Health check endpoint for Railway."""
    status = {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'firebase': 'unknown',
        'twilio': 'configured' if os.environ.get('TWILIO_ACCOUNT_SID') else 'not_configured'
    }

    try:
        db = get_db()
        db.collection('users').limit(1).get()
        status['firebase'] = 'connected'
    except Exception as e:
        status['firebase'] = 'disconnected'
        status['status'] = 'unhealthy'
        logger.error(f"Firebase health check failed: {e}")

    status_code = 200 if status['status'] == 'healthy' else 503
    return jsonify(status), status_code


@dashboard_bp.route('/')
@login_required
def index():
    """Main operator dashboard."""
    return render_template('dashboard.html', active_page='dashboard')


@dashboard_bp.route('/incoming')
@login_required
def incoming_messages():
    """Incoming messages view."""
    return render_template('incoming.html', active_page='incoming')


@dashboard_bp.route('/outgoing')
@login_required
def outgoing_messages():
    """Outgoing messages view."""
    return render_template('outgoing.html', active_page='outgoing')


@dashboard_bp.route('/send')
@login_required
def send_message():
    """Send message form."""
    return render_template('send.html', active_page='send')


@dashboard_bp.route('/users')
@login_required
def users():
    """Users list view."""
    return render_template('users.html', active_page='users')


@dashboard_bp.route('/simulate')
@login_required
def simulate():
    """Simulate incoming SMS page (simulation mode only)."""
    return render_template('simulate.html', active_page='simulate')

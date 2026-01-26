"""Dashboard routes."""

import logging
from datetime import datetime, timezone
import os

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, current_app

from services.firebase import get_db
from routes.auth import login_required

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Simple login page for operators."""
    if request.method == 'POST':
        password = request.form.get('password', '')
        operator_password = current_app.config.get('OPERATOR_PASSWORD', 'admin')

        if password == operator_password:
            session['operator_id'] = 'operator_default'
            session['operator_name'] = 'Operator'
            logger.info("Operator logged in")
            return redirect(url_for('dashboard.index'))
        else:
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
    return render_template('dashboard.html')


@dashboard_bp.route('/incoming')
@login_required
def incoming_messages():
    """Incoming messages view."""
    return render_template('incoming.html')


@dashboard_bp.route('/outgoing')
@login_required
def outgoing_messages():
    """Outgoing messages view."""
    return render_template('outgoing.html')


@dashboard_bp.route('/send')
@login_required
def send_message():
    """Send message form."""
    return render_template('send.html')


@dashboard_bp.route('/users')
@login_required
def users():
    """Users list view."""
    return render_template('users.html')


@dashboard_bp.route('/simulate')
@login_required
def simulate():
    """Simulate incoming SMS page (simulation mode only)."""
    return render_template('simulate.html')

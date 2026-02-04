"""
SMS Messaging UX - Main Application

A bidirectional SMS messaging system with operator dashboard.
"""

import os
import sys
import logging

from flask import Flask

from config import Config
from services.firebase import init_firebase
from routes import api_bp, dashboard_bp, webhooks_bp


def configure_logging():
    """Configure logging to send errors to stderr, everything else to stdout."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Format for all handlers
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler for INFO and below -> stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(lambda record: record.levelno < logging.ERROR)
    stdout_handler.setFormatter(formatter)

    # Handler for ERROR and above -> stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(formatter)

    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)


configure_logging()
logger = logging.getLogger(__name__)


def create_app():
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize Firebase
    with app.app_context():
        init_firebase(app)

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(webhooks_bp)

    logger.info("Application initialized")
    return app


# Create app instance
app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

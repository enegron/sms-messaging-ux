"""
SMS Messaging UX - Main Application

A bidirectional SMS messaging system with operator dashboard.
"""

import os
import logging

from flask import Flask

from config import Config
from services.firebase import init_firebase
from routes import api_bp, dashboard_bp, webhooks_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
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

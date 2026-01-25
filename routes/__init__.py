"""Routes package."""

from routes.api import api_bp
from routes.dashboard import dashboard_bp
from routes.webhooks import webhooks_bp

__all__ = ['api_bp', 'dashboard_bp', 'webhooks_bp']

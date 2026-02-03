"""Firebase Firestore service."""

import logging

import firebase_admin
from firebase_admin import credentials, firestore
from flask import current_app

logger = logging.getLogger(__name__)

# Global db instance
_db = None


def init_firebase(app):
    """Initialize Firebase Admin SDK using app config."""
    global _db

    if firebase_admin._apps:
        _db = firestore.client()
        return _db

    cred_dict = {
        "type": "service_account",
        "project_id": app.config.get('FIREBASE_PROJECT_ID'),
        "private_key_id": app.config.get('FIREBASE_PRIVATE_KEY_ID'),
        "private_key": app.config.get('FIREBASE_PRIVATE_KEY'),
        "client_email": app.config.get('FIREBASE_CLIENT_EMAIL'),
        "client_id": app.config.get('FIREBASE_CLIENT_ID'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": app.config.get('FIREBASE_CLIENT_CERT_URL', '')
    }

    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    _db = firestore.client()

    logger.info("Firebase initialized successfully")
    return _db


def get_db():
    """Get Firestore database client."""
    global _db
    if _db is None:
        raise RuntimeError("Firebase not initialized. Call init_firebase first.")
    return _db


def get_operator_password_hash():
    """Get the hashed operator password from Firestore.

    Returns:
        str or None: The hashed password, or None if not set.
    """
    db = get_db()
    doc = db.collection('config').document('operator_auth').get()
    if doc.exists:
        data = doc.to_dict()
        return data.get('password_hash')
    return None


def set_operator_password_hash(password_hash):
    """Set the hashed operator password in Firestore.

    Args:
        password_hash: The hashed password to store.
    """
    db = get_db()
    db.collection('config').document('operator_auth').set({
        'password_hash': password_hash,
        'updated_at': firestore.SERVER_TIMESTAMP
    }, merge=True)

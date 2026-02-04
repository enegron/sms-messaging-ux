"""Firebase Firestore service."""

import hashlib
import logging

import firebase_admin
from firebase_admin import credentials, firestore
from flask import current_app
from google.cloud.firestore_v1.base_query import FieldFilter

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


def hash_phone_number(phone_number):
    """Create a SHA256 hash of a phone number for anonymous logging.

    Used for unknown/unregistered numbers to allow correlation without
    storing the actual phone number (PII).

    Args:
        phone_number: Phone number in E.164 format.

    Returns:
        str: SHA256 hash prefixed with 'unknown_' for clarity.
    """
    hash_value = hashlib.sha256(phone_number.encode()).hexdigest()[:16]
    return f"unknown_{hash_value}"


def get_user_by_phone(phone_number):
    """Look up a user by phone number (document ID).

    Args:
        phone_number: Phone number in E.164 format (which is the document ID).

    Returns:
        tuple: (user_id (UUID), phone_number, user_data) if found, (None, None, None) if not found.
    """
    db = get_db()
    doc = db.collection('users').document(phone_number).get()
    if doc.exists:
        data = doc.to_dict()
        return data.get('userId'), doc.id, data
    return None, None, None


def get_user_by_uuid(user_uuid):
    """Look up a user by their UUID userId field.

    Args:
        user_uuid: The user's UUID (stored in userId field).

    Returns:
        tuple: (phone_number, user_data) if found, (None, None) if not found.
    """
    db = get_db()
    # Query for user with matching userId
    query = db.collection('users').where(filter=FieldFilter('userId', '==', user_uuid)).limit(1)
    docs = list(query.stream())
    if docs:
        doc = docs[0]
        return doc.id, doc.to_dict()  # doc.id is the phone number
    return None, None


def mask_phone_number(phone_number):
    """Mask a phone number to show only last 4 digits.

    Args:
        phone_number: Phone number in E.164 format (e.g., +12025551234).

    Returns:
        str: Masked phone number (e.g., ***-***-1234).
    """
    if not phone_number or len(phone_number) < 4:
        return "***"
    return f"***-***-{phone_number[-4:]}"


def get_user_display_info(user_uuid):
    """Get display-safe user information by UUID (no full phone number).

    Args:
        user_uuid: The user's UUID.

    Returns:
        dict: Display-safe user info with masked phone, or None if not found.
    """
    if user_uuid and user_uuid.startswith('unknown_'):
        # Unknown/hashed number
        return {
            'userId': user_uuid,
            'name': '',
            'maskedPhone': '(unknown)',
            'status': 'unknown'
        }

    phone_number, user_data = get_user_by_uuid(user_uuid)
    if user_data:
        return {
            'userId': user_uuid,
            'name': user_data.get('name', ''),
            'maskedPhone': mask_phone_number(phone_number),
            'status': user_data.get('status', '')
        }
    return None

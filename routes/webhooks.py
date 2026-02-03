"""Twilio webhook endpoints."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, request
from twilio.twiml.messaging_response import MessagingResponse

from services.firebase import get_db, get_user_by_phone, hash_phone_number
from services.twilio_sms import send_sms

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/twilio')


@webhooks_bp.route('/incoming', methods=['POST'])
def incoming():
    """
    Receive incoming SMS messages from Twilio.
    POST /twilio/incoming

    Logs messages using userId (not phone number) for privacy.
    Unknown numbers are logged with a hashed identifier.
    """
    try:
        # Parse Twilio webhook data
        phone_number = request.form.get('From', '')
        message_content = request.form.get('Body', '')
        message_sid = request.form.get('MessageSid', '')

        logger.info(f"POST /twilio/incoming received")

        db = get_db()

        # Look up user by phone number
        user_id, user_data = get_user_by_phone(phone_number)
        is_registered = user_id is not None and user_data.get('status') == 'active'
        response_sent = False

        # If registered, send acknowledgment
        if is_registered:
            try:
                send_sms(phone_number, "Your number is recognized. Message received.")
                response_sent = True
                logger.info(f"Acknowledgment sent to user {user_id[:8]}...")
            except Exception as e:
                logger.error(f"Failed to send acknowledgment: {e}")

        # Determine identifier for logging (userId or hashed phone for unknown)
        log_identifier = user_id if is_registered else hash_phone_number(phone_number)

        # Log incoming message to Firestore (NO phone number stored)
        incoming_message = {
            'timestamp': datetime.now(timezone.utc),
            'userId': log_identifier,
            'messageContent': message_content,
            'isRegistered': is_registered,
            'responseSent': response_sent,
            'twilio_SmsMessageSid': message_sid,
            'simulated': False
        }

        db.collection('incomingMessages').add(incoming_message)
        logger.info(f"Incoming message logged: registered={is_registered}")

        # Return empty TwiML response
        response = MessagingResponse()
        return str(response), 200, {'Content-Type': 'application/xml'}

    except Exception as e:
        logger.error(f"Error processing incoming message: {e}")
        # Still return 200 to Twilio to prevent retries
        response = MessagingResponse()
        return str(response), 200, {'Content-Type': 'application/xml'}


@webhooks_bp.route('/status', methods=['POST'])
def status():
    """Receive delivery status updates from Twilio (stub for future)."""
    logger.info("Twilio status callback received")
    return '', 200

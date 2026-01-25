"""Twilio webhook endpoints."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, request
from twilio.twiml.messaging_response import MessagingResponse

from services.firebase import get_db
from services.twilio_sms import send_sms

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/twilio')


@webhooks_bp.route('/incoming', methods=['POST'])
def incoming():
    """
    Receive incoming SMS messages from Twilio.
    POST /twilio/incoming
    """
    try:
        # Parse Twilio webhook data
        phone_number = request.form.get('From', '')
        message_content = request.form.get('Body', '')
        message_sid = request.form.get('MessageSid', '')

        logger.info(f"POST /twilio/incoming from:{phone_number}")

        db = get_db()

        # Check if user is registered and active
        user_doc = db.collection('users').document(phone_number).get()
        is_registered = user_doc.exists and user_doc.to_dict().get('status') == 'active'
        response_sent = False

        # If registered, send acknowledgment
        if is_registered:
            try:
                send_sms(phone_number, "Your number is recognized. Message received.")
                response_sent = True
                logger.info(f"Acknowledgment sent to {phone_number}")
            except Exception as e:
                logger.error(f"Failed to send acknowledgment: {e}")

        # Log incoming message to Firestore
        incoming_message = {
            'timestamp': datetime.now(timezone.utc),
            'phoneNumber': phone_number,
            'messageContent': message_content,
            'isRegistered': is_registered,
            'responseSent': response_sent,
            'twilio_SmsMessageSid': message_sid
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

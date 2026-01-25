"""Twilio SMS service."""

import logging
import os

from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)

# Global client instance
_client = None


def init_twilio():
    """Initialize Twilio client."""
    global _client

    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')

    if account_sid and auth_token:
        _client = TwilioClient(account_sid, auth_token)
        logger.info("Twilio client initialized")
    else:
        logger.warning("Twilio credentials not configured")


def get_twilio_client():
    """Get Twilio client instance."""
    global _client
    if _client is None:
        init_twilio()
    return _client


def send_sms(to_number, message_body):
    """
    Send an SMS message.

    Args:
        to_number: Recipient phone number (E.164 format)
        message_body: Message text

    Returns:
        Twilio message object with .sid attribute

    Raises:
        Exception if sending fails
    """
    client = get_twilio_client()
    from_number = os.environ.get('TWILIO_PHONE_NUMBER')

    message = client.messages.create(
        body=message_body,
        from_=from_number,
        to=to_number
    )

    logger.info(f"SMS sent to {to_number}, SID: {message.sid}")
    return message

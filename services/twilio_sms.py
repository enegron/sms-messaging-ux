"""Twilio SMS service."""

import logging
import os
import uuid

from twilio.rest import Client as TwilioClient

from services.firebase import mask_phone_number

logger = logging.getLogger(__name__)

# Global client instance
_client = None


def is_simulation_mode():
    """Check if simulation mode is enabled."""
    return os.environ.get('SIMULATION_MODE', 'false').lower() == 'true'


def init_twilio():
    """Initialize Twilio client."""
    global _client

    if is_simulation_mode():
        logger.info("Simulation mode enabled - Twilio client not initialized")
        return

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
    if _client is None and not is_simulation_mode():
        init_twilio()
    return _client


class SimulatedMessage:
    """Simulated Twilio message object for simulation mode."""

    def __init__(self, to_number, message_body, status='sent'):
        self.sid = f"SIM{uuid.uuid4().hex[:30]}"
        self.to = to_number
        self.body = message_body
        self.status = status


def send_sms(to_number, message_body, simulate_status='sent'):
    """
    Send an SMS message.

    Args:
        to_number: Recipient phone number (E.164 format)
        message_body: Message text
        simulate_status: Status to simulate ('sent', 'failed', 'queued') - only used in simulation mode

    Returns:
        Twilio message object (or SimulatedMessage in simulation mode) with .sid attribute

    Raises:
        Exception if sending fails (in production mode)
        SimulatedFailure if simulate_status is 'failed' (in simulation mode)
    """
    if is_simulation_mode():
        logger.info(f"[SIMULATION] SMS to {mask_phone_number(to_number)}: {message_body[:50]}...")

        if simulate_status == 'failed':
            raise SimulatedFailure("Simulated send failure")

        message = SimulatedMessage(to_number, message_body, status=simulate_status)
        logger.info(f"[SIMULATION] SMS logged with SID: {message.sid}, status: {simulate_status}")
        return message

    # Production mode - real Twilio API call
    client = get_twilio_client()
    from_number = os.environ.get('TWILIO_PHONE_NUMBER')

    message = client.messages.create(
        body=message_body,
        from_=from_number,
        to=to_number
    )

    logger.info(f"SMS sent to {mask_phone_number(to_number)}, SID: {message.sid}")
    return message


class SimulatedFailure(Exception):
    """Exception raised when simulating a failed SMS send."""
    pass

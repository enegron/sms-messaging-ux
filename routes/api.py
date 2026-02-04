"""API endpoints."""

import re
import logging
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, session
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from services.firebase import (
    get_db, get_user_by_phone, get_user_by_uuid,
    hash_phone_number, mask_phone_number, get_user_display_info
)
from services.twilio_sms import send_sms, is_simulation_mode, SimulatedFailure
from routes.auth import login_required

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


def is_valid_e164(phone_number):
    """Validate phone number is in E.164 format."""
    pattern = r'^\+[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone_number))


def is_valid_uuid(value):
    """Check if value looks like a UUID."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


@api_bp.route('/config', methods=['GET'])
@login_required
def get_config():
    """
    Get current configuration.
    GET /api/config
    """
    return jsonify({
        'simulationMode': is_simulation_mode()
    }), 200


@api_bp.route('/send-message', methods=['POST'])
@login_required
def send_message():
    """
    Send an SMS to a registered user.
    POST /api/send-message
    Body: {"userId": "uuid-here", "messageContent": "...", "simulateStatus": "sent"}

    Note: userId is the user's UUID. Phone number is looked up internally.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'invalid_request', 'message': 'JSON body required'}), 400

        user_id = data.get('userId', '')
        message_content = data.get('messageContent', '')
        operator_id = data.get('operatorId', session.get('operator_id', 'unknown'))
        operator_name = session.get('operator_name', 'Unknown Operator')
        simulate_status = data.get('simulateStatus', 'sent')

        # Validate userId is a UUID
        if not is_valid_uuid(user_id):
            return jsonify({
                'error': 'invalid_user_id',
                'message': 'User ID must be a valid UUID'
            }), 400

        # Validate message content
        if not message_content or not message_content.strip():
            return jsonify({
                'error': 'invalid_message',
                'message': 'Message content cannot be empty'
            }), 400

        db = get_db()
        simulated = is_simulation_mode()

        # Look up user by UUID to get phone number
        phone_number, user_data = get_user_by_uuid(user_id)

        if not user_data:
            return jsonify({
                'error': 'user_not_found',
                'message': 'User not found'
            }), 404

        if user_data.get('status') != 'active':
            return jsonify({
                'error': 'user_inactive',
                'message': 'User status is not active'
            }), 403

        # Create outgoing message record (UUID userId, no phone number)
        queued_at = datetime.now(timezone.utc)
        outgoing_message = {
            'queuedAt': queued_at,
            'sentAt': None,
            'userId': user_id,  # UUID, not phone number
            'messageContent': message_content,
            'operatorId': operator_id,
            'operatorName': operator_name,
            'status': 'queued',
            'twilio_SmsMessageSid': None,
            'twilio_ErrorMessage': None,
            'simulated': simulated
        }

        # Add to Firestore first
        doc_ref = db.collection('outgoingMessages').add(outgoing_message)
        message_id = doc_ref[1].id

        # Send via Twilio (or simulate) - phone_number used in memory only
        try:
            twilio_message = send_sms(phone_number, message_content, simulate_status=simulate_status)

            # Update record with sent status
            sent_at = datetime.now(timezone.utc)
            final_status = simulate_status if simulated else 'sent'
            db.collection('outgoingMessages').document(message_id).update({
                'status': final_status,
                'sentAt': sent_at,
                'twilio_SmsMessageSid': twilio_message.sid
            })

            logger.info(f"POST /api/send-message 200 {operator_id} simulated={simulated}")

            return jsonify({
                'status': final_status,
                'messageId': message_id,
                'userId': user_id,
                'userName': user_data.get('name', ''),
                'maskedPhone': mask_phone_number(phone_number),
                'timestamp': sent_at.isoformat(),
                'twilio_MessageSid': twilio_message.sid,
                'simulated': simulated
            }), 200

        except (Exception, SimulatedFailure) as e:
            # Update record with failed status
            db.collection('outgoingMessages').document(message_id).update({
                'status': 'failed',
                'twilio_ErrorMessage': str(e)
            })

            logger.error(f"Send failed: {e} simulated={simulated}")
            return jsonify({
                'error': 'send_error',
                'message': 'Failed to send SMS',
                'details': str(e),
                'simulated': simulated
            }), 503

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return jsonify({
            'error': 'server_error',
            'message': str(e)
        }), 500


@api_bp.route('/messages/incoming', methods=['GET'])
@login_required
def get_incoming_messages():
    """
    Get all incoming messages.
    GET /api/messages/incoming?limit=100&sort=desc&userId=...&isRegistered=true
    Auto-filters by simulation mode.

    Returns userId (UUID) and user display info (masked phone), not full phone numbers.
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        sort_order = request.args.get('sort', 'desc')
        user_filter = request.args.get('userId', '')
        registered_filter = request.args.get('isRegistered', '')

        db = get_db()
        simulated = is_simulation_mode()

        query = db.collection('incomingMessages')

        # Auto-filter by simulation mode
        query = query.where(filter=FieldFilter('simulated', '==', simulated))

        # Apply filters
        if user_filter:
            query = query.where(filter=FieldFilter('userId', '==', user_filter))

        if registered_filter:
            is_reg = registered_filter.lower() == 'true'
            query = query.where(filter=FieldFilter('isRegistered', '==', is_reg))

        # Apply sorting
        direction = firestore.Query.DESCENDING if sort_order == 'desc' else firestore.Query.ASCENDING
        query = query.order_by('timestamp', direction=direction)

        # Apply limit
        query = query.limit(limit)

        # Execute query
        docs = query.stream()

        messages = []
        user_cache = {}  # Cache user lookups

        for doc in docs:
            data = doc.to_dict()
            user_id = data.get('userId', '')

            # Get user display info (with caching)
            if user_id not in user_cache:
                user_cache[user_id] = get_user_display_info(user_id)

            user_info = user_cache[user_id] or {
                'userId': user_id,
                'name': '',
                'maskedPhone': '(unknown)',
                'status': 'unknown'
            }

            messages.append({
                'id': doc.id,
                'timestamp': data.get('timestamp').isoformat() if data.get('timestamp') else None,
                'userId': user_id,
                'userName': user_info.get('name', ''),
                'maskedPhone': user_info.get('maskedPhone', ''),
                'messageContent': data.get('messageContent', ''),
                'isRegistered': data.get('isRegistered', False),
                'responseSent': data.get('responseSent', False),
                'twilio_SmsMessageSid': data.get('twilio_SmsMessageSid', ''),
                'simulated': data.get('simulated', False)
            })

        return jsonify({
            'status': 'success',
            'count': len(messages),
            'messages': messages,
            'simulationMode': simulated
        }), 200

    except Exception as e:
        logger.error(f"Error fetching incoming messages: {e}")
        return jsonify({
            'error': 'query_failed',
            'message': 'Failed to fetch messages from database'
        }), 500


@api_bp.route('/messages/outgoing', methods=['GET'])
@login_required
def get_outgoing_messages():
    """
    Get all outgoing messages.
    GET /api/messages/outgoing?limit=100&sort=desc&userId=...&status=sent&operatorId=...
    Auto-filters by simulation mode.

    Returns userId (UUID) and user display info (masked phone), not full phone numbers.
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        sort_order = request.args.get('sort', 'desc')
        user_filter = request.args.get('userId', '')
        status_filter = request.args.get('status', '')
        operator_filter = request.args.get('operatorId', '')

        db = get_db()
        simulated = is_simulation_mode()

        query = db.collection('outgoingMessages')

        # Auto-filter by simulation mode
        query = query.where(filter=FieldFilter('simulated', '==', simulated))

        # Apply filters
        if user_filter:
            query = query.where(filter=FieldFilter('userId', '==', user_filter))

        if status_filter:
            query = query.where(filter=FieldFilter('status', '==', status_filter))

        if operator_filter:
            query = query.where(filter=FieldFilter('operatorId', '==', operator_filter))

        # Apply sorting (use queuedAt since sentAt may be null)
        direction = firestore.Query.DESCENDING if sort_order == 'desc' else firestore.Query.ASCENDING
        query = query.order_by('queuedAt', direction=direction)

        # Apply limit
        query = query.limit(limit)

        # Execute query
        docs = query.stream()

        messages = []
        user_cache = {}  # Cache user lookups

        for doc in docs:
            data = doc.to_dict()
            user_id = data.get('userId', '')

            # Get user display info (with caching)
            if user_id not in user_cache:
                user_cache[user_id] = get_user_display_info(user_id)

            user_info = user_cache[user_id] or {
                'userId': user_id,
                'name': '',
                'maskedPhone': '(unknown)',
                'status': 'unknown'
            }

            messages.append({
                'id': doc.id,
                'queuedAt': data.get('queuedAt').isoformat() if data.get('queuedAt') else None,
                'sentAt': data.get('sentAt').isoformat() if data.get('sentAt') else None,
                'userId': user_id,
                'userName': user_info.get('name', ''),
                'maskedPhone': user_info.get('maskedPhone', ''),
                'messageContent': data.get('messageContent', ''),
                'operatorId': data.get('operatorId', ''),
                'operatorName': data.get('operatorName', ''),
                'status': data.get('status', ''),
                'twilio_SmsMessageSid': data.get('twilio_SmsMessageSid', ''),
                'twilio_ErrorMessage': data.get('twilio_ErrorMessage', ''),
                'simulated': data.get('simulated', False)
            })

        return jsonify({
            'status': 'success',
            'count': len(messages),
            'messages': messages,
            'simulationMode': simulated
        }), 200

    except Exception as e:
        logger.error(f"Error fetching outgoing messages: {e}")
        return jsonify({
            'error': 'query_failed',
            'message': 'Failed to fetch messages from database'
        }), 500


@api_bp.route('/users', methods=['GET'])
@login_required
def get_users():
    """
    Get all registered users.
    GET /api/users?status=active

    Returns userId (UUID) and masked phone, not full phone numbers.
    """
    try:
        status_filter = request.args.get('status', 'active')

        db = get_db()
        query = db.collection('users')

        # Apply status filter (unless 'all')
        if status_filter != 'all':
            query = query.where(filter=FieldFilter('status', '==', status_filter))

        # Execute query
        docs = query.stream()

        users = []
        for doc in docs:
            data = doc.to_dict()
            phone_number = doc.id  # Phone number is the document ID
            user_id = data.get('userId', '')  # UUID
            users.append({
                'userId': user_id,
                'name': data.get('name', ''),
                'maskedPhone': mask_phone_number(phone_number),
                'status': data.get('status', ''),
                'createdAt': data.get('createdAt').isoformat() if data.get('createdAt') else None
            })

        # Sort by name or masked phone
        users.sort(key=lambda x: x.get('name') or x.get('maskedPhone', ''))

        return jsonify({
            'status': 'success',
            'count': len(users),
            'users': users
        }), 200

    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return jsonify({
            'error': 'query_failed',
            'message': 'Failed to fetch users from database'
        }), 500


@api_bp.route('/simulate/incoming', methods=['POST'])
@login_required
def simulate_incoming():
    """
    Simulate an incoming SMS message (only works in simulation mode).
    POST /api/simulate/incoming
    Body: {"userId": "uuid-here", "messageContent": "..."} for registered user
          {"phoneNumber": "+1...", "messageContent": "..."} for unknown number

    Note: For simulation of unknown numbers, phoneNumber is used to generate hash.
    For registered users, userId (UUID) is used.
    """
    if not is_simulation_mode():
        return jsonify({
            'error': 'not_allowed',
            'message': 'This endpoint is only available in simulation mode'
        }), 403

    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'invalid_request', 'message': 'JSON body required'}), 400

        user_id = data.get('userId', '')
        phone_number = data.get('phoneNumber', '')
        message_content = data.get('messageContent', '')

        db = get_db()
        is_registered = False
        response_sent = False
        log_identifier = None
        phone_for_twilio = None
        user_data = None

        # Check if userId is a UUID (registered user) or if we have a phoneNumber (unknown)
        if user_id and is_valid_uuid(user_id):
            # Look up registered user by UUID
            phone_for_twilio, user_data = get_user_by_uuid(user_id)
            if user_data and user_data.get('status') == 'active':
                is_registered = True
                log_identifier = user_id  # Use UUID

        if not is_registered and phone_number:
            # Unknown number - validate and hash it
            if not is_valid_e164(phone_number):
                return jsonify({
                    'error': 'invalid_phone_number',
                    'message': 'Phone number must be in E.164 format (+1234567890)'
                }), 400
            log_identifier = hash_phone_number(phone_number)
            phone_for_twilio = phone_number

        if not log_identifier:
            return jsonify({
                'error': 'invalid_request',
                'message': 'Either userId (UUID) or phoneNumber required'
            }), 400

        # If registered, simulate sending acknowledgment
        if is_registered and phone_for_twilio:
            try:
                ack_message = send_sms(phone_for_twilio, "Your number is recognized. Message received.")
                response_sent = True
                logger.info(f"[SIMULATION] Acknowledgment logged for user")

                # Log the outgoing acknowledgment (UUID userId, no phone number)
                ack_record = {
                    'queuedAt': datetime.now(timezone.utc),
                    'sentAt': datetime.now(timezone.utc),
                    'userId': user_id,  # UUID
                    'messageContent': "Your number is recognized. Message received.",
                    'operatorId': 'system',
                    'operatorName': 'System (Auto-reply)',
                    'status': 'sent',
                    'twilio_SmsMessageSid': ack_message.sid,
                    'twilio_ErrorMessage': None,
                    'simulated': True
                }
                db.collection('outgoingMessages').add(ack_record)

            except Exception as e:
                logger.error(f"[SIMULATION] Failed to log acknowledgment: {e}")

        # Log incoming message to Firestore (UUID or hash, no phone number)
        incoming_message = {
            'timestamp': datetime.now(timezone.utc),
            'userId': log_identifier,  # UUID for registered, hash for unknown
            'messageContent': message_content,
            'isRegistered': is_registered,
            'responseSent': response_sent,
            'twilio_SmsMessageSid': f"SIM{uuid.uuid4().hex[:30]}",
            'simulated': True
        }

        doc_ref = db.collection('incomingMessages').add(incoming_message)
        message_id = doc_ref[1].id

        logger.info(f"[SIMULATION] Incoming message logged: registered={is_registered}")

        # Get display info for response
        if is_registered:
            display_info = get_user_display_info(user_id)
        else:
            display_info = {
                'userId': log_identifier,
                'name': '',
                'maskedPhone': '(unknown)',
                'status': 'unknown'
            }

        return jsonify({
            'status': 'success',
            'messageId': message_id,
            'userId': log_identifier,
            'userName': display_info.get('name', '') if display_info else '',
            'maskedPhone': display_info.get('maskedPhone', '') if display_info else '(unknown)',
            'isRegistered': is_registered,
            'responseSent': response_sent,
            'simulated': True
        }), 200

    except Exception as e:
        logger.error(f"Error simulating incoming message: {e}")
        return jsonify({
            'error': 'server_error',
            'message': str(e)
        }), 500

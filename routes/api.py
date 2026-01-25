"""API endpoints."""

import re
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, session
from firebase_admin import firestore

from services.firebase import get_db
from services.twilio_sms import send_sms
from routes.auth import login_required

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


def is_valid_e164(phone_number):
    """Validate phone number is in E.164 format."""
    pattern = r'^\+[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone_number))


@api_bp.route('/send-message', methods=['POST'])
@login_required
def send_message():
    """
    Send an SMS to a registered user.
    POST /api/send-message
    Body: {"phoneNumber": "+1...", "messageContent": "...", "operatorId": "..."}
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'invalid_request', 'message': 'JSON body required'}), 400

        phone_number = data.get('phoneNumber', '')
        message_content = data.get('messageContent', '')
        operator_id = data.get('operatorId', session.get('operator_id', 'unknown'))
        operator_name = session.get('operator_name', 'Unknown Operator')

        # Validate phone number format
        if not is_valid_e164(phone_number):
            return jsonify({
                'error': 'invalid_phone_number',
                'message': 'Phone number must be in E.164 format (+1234567890)'
            }), 400

        # Validate message content
        if not message_content or not message_content.strip():
            return jsonify({
                'error': 'invalid_message',
                'message': 'Message content cannot be empty'
            }), 400

        db = get_db()

        # Check if user exists and is active
        user_doc = db.collection('users').document(phone_number).get()

        if not user_doc.exists:
            return jsonify({
                'error': 'user_not_found',
                'message': f'Phone number {phone_number} is not registered'
            }), 404

        user_data = user_doc.to_dict()
        if user_data.get('status') != 'active':
            return jsonify({
                'error': 'user_inactive',
                'message': 'User status is not active'
            }), 403

        # Create outgoing message record (queued)
        queued_at = datetime.now(timezone.utc)
        outgoing_message = {
            'queuedAt': queued_at,
            'sentAt': None,
            'phoneNumber': phone_number,
            'messageContent': message_content,
            'operatorId': operator_id,
            'operatorName': operator_name,
            'status': 'queued',
            'twilio_SmsMessageSid': None,
            'twilio_ErrorMessage': None
        }

        # Add to Firestore first
        doc_ref = db.collection('outgoingMessages').add(outgoing_message)
        message_id = doc_ref[1].id

        # Send via Twilio
        try:
            twilio_message = send_sms(phone_number, message_content)

            # Update record with sent status
            sent_at = datetime.now(timezone.utc)
            db.collection('outgoingMessages').document(message_id).update({
                'status': 'sent',
                'sentAt': sent_at,
                'twilio_SmsMessageSid': twilio_message.sid
            })

            logger.info(f"POST /api/send-message 200 {operator_id}")

            return jsonify({
                'status': 'sent',
                'messageId': message_id,
                'phoneNumber': phone_number,
                'timestamp': sent_at.isoformat(),
                'twilio_MessageSid': twilio_message.sid
            }), 200

        except Exception as e:
            # Update record with failed status
            db.collection('outgoingMessages').document(message_id).update({
                'status': 'failed',
                'twilio_ErrorMessage': str(e)
            })

            logger.error(f"Twilio send failed: {e}")
            return jsonify({
                'error': 'twilio_error',
                'message': 'Failed to send SMS',
                'details': str(e)
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
    GET /api/messages/incoming?limit=100&sort=desc&phoneNumber=...&isRegistered=true
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        sort_order = request.args.get('sort', 'desc')
        phone_filter = request.args.get('phoneNumber', '')
        registered_filter = request.args.get('isRegistered', '')

        db = get_db()
        query = db.collection('incomingMessages')

        # Apply filters
        if phone_filter:
            query = query.where('phoneNumber', '==', phone_filter)

        if registered_filter:
            is_reg = registered_filter.lower() == 'true'
            query = query.where('isRegistered', '==', is_reg)

        # Apply sorting
        direction = firestore.Query.DESCENDING if sort_order == 'desc' else firestore.Query.ASCENDING
        query = query.order_by('timestamp', direction=direction)

        # Apply limit
        query = query.limit(limit)

        # Execute query
        docs = query.stream()

        messages = []
        for doc in docs:
            data = doc.to_dict()
            messages.append({
                'id': doc.id,
                'timestamp': data.get('timestamp').isoformat() if data.get('timestamp') else None,
                'phoneNumber': data.get('phoneNumber', ''),
                'messageContent': data.get('messageContent', ''),
                'isRegistered': data.get('isRegistered', False),
                'responseSent': data.get('responseSent', False),
                'twilio_SmsMessageSid': data.get('twilio_SmsMessageSid', '')
            })

        return jsonify({
            'status': 'success',
            'count': len(messages),
            'messages': messages
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
    GET /api/messages/outgoing?limit=100&sort=desc&phoneNumber=...&status=sent&operatorId=...
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        sort_order = request.args.get('sort', 'desc')
        phone_filter = request.args.get('phoneNumber', '')
        status_filter = request.args.get('status', '')
        operator_filter = request.args.get('operatorId', '')

        db = get_db()
        query = db.collection('outgoingMessages')

        # Apply filters
        if phone_filter:
            query = query.where('phoneNumber', '==', phone_filter)

        if status_filter:
            query = query.where('status', '==', status_filter)

        if operator_filter:
            query = query.where('operatorId', '==', operator_filter)

        # Apply sorting (use queuedAt since sentAt may be null)
        direction = firestore.Query.DESCENDING if sort_order == 'desc' else firestore.Query.ASCENDING
        query = query.order_by('queuedAt', direction=direction)

        # Apply limit
        query = query.limit(limit)

        # Execute query
        docs = query.stream()

        messages = []
        for doc in docs:
            data = doc.to_dict()
            messages.append({
                'id': doc.id,
                'queuedAt': data.get('queuedAt').isoformat() if data.get('queuedAt') else None,
                'sentAt': data.get('sentAt').isoformat() if data.get('sentAt') else None,
                'phoneNumber': data.get('phoneNumber', ''),
                'messageContent': data.get('messageContent', ''),
                'operatorId': data.get('operatorId', ''),
                'operatorName': data.get('operatorName', ''),
                'status': data.get('status', ''),
                'twilio_SmsMessageSid': data.get('twilio_SmsMessageSid', ''),
                'twilio_ErrorMessage': data.get('twilio_ErrorMessage', '')
            })

        return jsonify({
            'status': 'success',
            'count': len(messages),
            'messages': messages
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
    """
    try:
        status_filter = request.args.get('status', 'active')

        db = get_db()
        query = db.collection('users')

        # Apply status filter (unless 'all')
        if status_filter != 'all':
            query = query.where('status', '==', status_filter)

        # Execute query
        docs = query.stream()

        users = []
        for doc in docs:
            data = doc.to_dict()
            users.append({
                'phoneNumber': data.get('phoneNumber', doc.id),
                'name': data.get('name', ''),
                'status': data.get('status', ''),
                'createdAt': data.get('createdAt').isoformat() if data.get('createdAt') else None
            })

        # Sort by name or phone
        users.sort(key=lambda x: x.get('name') or x.get('phoneNumber', ''))

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

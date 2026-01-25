# API & Webhook Specifications

## Overview

This document specifies all HTTP endpoints and webhooks for the SMS Messaging UX system.

**Base URL (Railway):** `https://your-railway-app.railway.app` (will be assigned by Railway)

---

## 1. Incoming SMS Webhook (Twilio → Backend)

### Endpoint: `POST /twilio/incoming`

**Purpose:** Receive incoming SMS messages from Twilio

**Triggered by:** Twilio detects incoming SMS to your number → forwards to this webhook

**Request format:**

Twilio sends a POST request with URL-encoded form data:

```
POST /twilio/incoming HTTP/1.1
Host: your-railway-app.railway.app
Content-Type: application/x-www-form-urlencoded

MessageSid=SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
&AccountSid=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
&From=%2B12025551234
&To=%2B12025554567
&Body=Hello+testing+the+system
&NumMedia=0
```

**Request body fields (form-encoded):**

| Field | Type | Required | Example | Notes |
|-------|------|----------|---------|-------|
| `MessageSid` | string | Yes | `SM7XXXXXXXXXXXX` | Twilio's unique message ID |
| `AccountSid` | string | Yes | `ACXXXXXXXXXXXX` | Twilio account ID (validate against env var) |
| `From` | string | Yes | `+12025551234` | Sending phone number (URL-encoded, include +) |
| `To` | string | Yes | `+12025554567` | Receiving number (your inbound number) |
| `Body` | string | Yes | `Hello testing` | Message content (can be empty string) |
| `NumMedia` | integer | Yes | `0` | Number of media attachments (MVP ignores) |

**Response format:**

Backend must respond with HTTP 200 OK. Twilio expects a TwiML XML response (but plain text is acceptable):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response></Response>
```

Or plain 200 OK with no body.

**Processing logic:**

```
1. Parse incoming request
2. Extract From (phoneNumber), Body (messageContent), MessageSid
3. Query Firebase users collection for document with ID = phoneNumber
4. If user found AND status = "active":
     a. Create document in incomingMessages collection
        - timestamp: now
        - phoneNumber
        - messageContent
        - isRegistered: true
        - responseSent: true
        - twilio_SmsMessageSid: MessageSid
     b. Send acknowledgment SMS via Twilio API
        - TO: phoneNumber
        - TEXT: "Your number is recognized. Message received."
5. If user not found OR status != "active":
     a. Create document in incomingMessages collection
        - timestamp: now
        - phoneNumber
        - messageContent
        - isRegistered: false
        - responseSent: false
        - twilio_SmsMessageSid: MessageSid
     b. Do NOT send any response SMS
6. Return HTTP 200 OK
```

**Error handling:**

- If Firebase write fails: Log error, return HTTP 200 anyway (Twilio doesn't care)
- If Twilio send SMS fails: Log error, return HTTP 200, operator will see in dashboard
- If parsing fails: Return HTTP 400 Bad Request

**Example curl (for testing):**

```bash
curl -X POST http://localhost:5000/twilio/incoming \
  -d "MessageSid=SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -d "AccountSid=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -d "From=%2B12025551234" \
  -d "To=%2B12025554567" \
  -d "Body=Hello+testing" \
  -d "NumMedia=0"
```

---

## 2. Outgoing SMS Send Endpoint

### Endpoint: `POST /api/send-message`

**Purpose:** Send an SMS from operator to a registered user

**Triggered by:** Operator clicks "Send" on dashboard

**Request format (JSON):**

```json
POST /api/send-message HTTP/1.1
Host: your-railway-app.railway.app
Content-Type: application/json
Authorization: Bearer <operator_token> (or session-based for MVP)

{
  "phoneNumber": "+12025551234",
  "messageContent": "Your order has been shipped!",
  "operatorId": "operator_alice"
}
```

**Request body fields:**

| Field | Type | Required | Example | Notes |
|-------|------|----------|---------|-------|
| `phoneNumber` | string | Yes | `+12025551234` | Recipient (E.164 format) |
| `messageContent` | string | Yes | `Your order...` | Message text (1-1600 chars) |
| `operatorId` | string | Yes | `operator_alice` | Who is sending (for audit) |

**Validation:**

- `phoneNumber` must be in E.164 format
- `phoneNumber` must exist in users collection with status = "active"
- `messageContent` must not be empty
- `operatorId` must not be empty
- Operator must be authenticated (implementation detail for MVP)

**Response format (JSON):**

**Success (HTTP 200):**

```json
{
  "status": "sent",
  "messageId": "out_1234567890",
  "phoneNumber": "+12025551234",
  "timestamp": "2025-01-15T14:25:12.456Z",
  "twilio_MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

**Error - User not found (HTTP 404):**

```json
{
  "error": "user_not_found",
  "message": "Phone number +12025551234 is not registered"
}
```

**Error - User inactive (HTTP 403):**

```json
{
  "error": "user_inactive",
  "message": "User status is not active"
}
```

**Error - Invalid phone number (HTTP 400):**

```json
{
  "error": "invalid_phone_number",
  "message": "Phone number must be in E.164 format (+1234567890)"
}
```

**Error - Twilio failure (HTTP 503):**

```json
{
  "error": "twilio_error",
  "message": "Failed to send SMS",
  "details": "Account has insufficient credit"
}
```

**Processing logic:**

```
1. Validate request format (required fields, types)
2. Validate phoneNumber is E.164 format
3. Query Firebase users/{phoneNumber}
4. If not found: return 404
5. If found but status != "active": return 403
6. Create document in outgoingMessages:
   - queuedAt: now
   - sentAt: null (not yet sent)
   - phoneNumber
   - messageContent
   - operatorId
   - operatorName: (optional, look up from auth context)
   - status: "queued"
   - twilio_SmsMessageSid: null
   - twilio_ErrorMessage: null
7. Call Twilio API to send SMS
8. If Twilio returns MessageSid:
   a. Update outgoingMessages document:
      - status: "sent"
      - sentAt: now
      - twilio_SmsMessageSid: MessageSid
   b. Return HTTP 200 with success response
9. If Twilio returns error:
   a. Update outgoingMessages document:
      - status: "failed"
      - twilio_ErrorMessage: error details
   b. Return HTTP 503 with error response
```

**Example curl (for testing):**

```bash
curl -X POST http://localhost:5000/api/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "phoneNumber": "+12025551234",
    "messageContent": "Your order has been shipped!",
    "operatorId": "operator_alice"
  }'
```

---

## 3. Get Incoming Messages Endpoint

### Endpoint: `GET /api/messages/incoming`

**Purpose:** Fetch all incoming SMS messages for dashboard display

**Triggered by:** Operator loads dashboard or clicks "Refresh"

**Request format:**

```
GET /api/messages/incoming?limit=100&sort=desc HTTP/1.1
Host: your-railway-app.railway.app
Authorization: Bearer <operator_token> (or session-based)
```

**Query parameters:**

| Parameter | Type | Default | Example | Notes |
|-----------|------|---------|---------|-------|
| `limit` | integer | 100 | 50 | Max messages to return |
| `sort` | string | "desc" | "asc" | Sort order by timestamp |
| `phoneNumber` | string | optional | "+12025551234" | Filter by sender |
| `isRegistered` | boolean | optional | true | Filter by registration status |

**Response format (JSON):**

**Success (HTTP 200):**

```json
{
  "status": "success",
  "count": 5,
  "messages": [
    {
      "id": "msg_1234567890",
      "timestamp": "2025-01-15T14:23:45.123Z",
      "phoneNumber": "+12025551234",
      "messageContent": "Hello, testing the system",
      "isRegistered": true,
      "responseSent": true,
      "twilio_SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    },
    {
      "id": "msg_0987654321",
      "timestamp": "2025-01-15T13:15:20.456Z",
      "phoneNumber": "+19876543210",
      "messageContent": "",
      "isRegistered": false,
      "responseSent": false,
      "twilio_SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    }
  ]
}
```

**Error (HTTP 500):**

```json
{
  "error": "query_failed",
  "message": "Failed to fetch messages from database"
}
```

**Processing logic:**

```
1. Validate operator authentication
2. Build Firestore query for incomingMessages collection
   - Apply sort: timestamp (desc by default)
   - Apply filters: phoneNumber (if provided), isRegistered (if provided)
   - Apply limit
3. Execute query against Firebase
4. Format results and return HTTP 200
```

**Example curl:**

```bash
curl -X GET "http://localhost:5000/api/messages/incoming?limit=50&sort=desc" \
  -H "Authorization: Bearer operator_token"
```

---

## 4. Get Outgoing Messages Endpoint

### Endpoint: `GET /api/messages/outgoing`

**Purpose:** Fetch all outgoing SMS messages for dashboard display

**Triggered by:** Operator loads dashboard or clicks "Refresh"

**Request format:**

```
GET /api/messages/outgoing?limit=100&sort=desc HTTP/1.1
Host: your-railway-app.railway.app
Authorization: Bearer <operator_token> (or session-based)
```

**Query parameters:**

| Parameter | Type | Default | Example | Notes |
|-----------|------|---------|---------|-------|
| `limit` | integer | 100 | 50 | Max messages to return |
| `sort` | string | "desc" | "asc" | Sort order by timestamp |
| `phoneNumber` | string | optional | "+12025551234" | Filter by recipient |
| `status` | string | optional | "sent" | Filter by status |
| `operatorId` | string | optional | "operator_alice" | Filter by sender |

**Response format (JSON):**

**Success (HTTP 200):**

```json
{
  "status": "success",
  "count": 3,
  "messages": [
    {
      "id": "out_1234567890",
      "queuedAt": "2025-01-15T14:25:10.456Z",
      "sentAt": "2025-01-15T14:25:12.789Z",
      "phoneNumber": "+12025551234",
      "messageContent": "Your order has been shipped!",
      "operatorId": "operator_alice",
      "operatorName": "Alice Johnson",
      "status": "sent",
      "twilio_SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "twilio_ErrorMessage": null
    },
    {
      "id": "out_0987654321",
      "queuedAt": "2025-01-15T14:20:05.123Z",
      "sentAt": null,
      "phoneNumber": "+13105554567",
      "messageContent": "Test message",
      "operatorId": "operator_bob",
      "operatorName": "Bob Smith",
      "status": "failed",
      "twilio_SmsMessageSid": null,
      "twilio_ErrorMessage": "Invalid phone number"
    }
  ]
}
```

**Error (HTTP 500):**

```json
{
  "error": "query_failed",
  "message": "Failed to fetch messages from database"
}
```

**Processing logic:**

```
1. Validate operator authentication
2. Build Firestore query for outgoingMessages collection
   - Apply sort: sentAt or queuedAt (desc by default)
   - Apply filters: phoneNumber, status, operatorId (if provided)
   - Apply limit
3. Execute query against Firebase
4. Format results and return HTTP 200
```

**Example curl:**

```bash
curl -X GET "http://localhost:5000/api/messages/outgoing?limit=50&status=sent" \
  -H "Authorization: Bearer operator_token"
```

---

## 5. Get Users Endpoint

### Endpoint: `GET /api/users`

**Purpose:** Fetch all registered users for dropdown in send message form

**Triggered by:** Dashboard loads, operator opens send message form

**Request format:**

```
GET /api/users?status=active HTTP/1.1
Host: your-railway-app.railway.app
Authorization: Bearer <operator_token> (or session-based)
```

**Query parameters:**

| Parameter | Type | Default | Example | Notes |
|-----------|------|---------|---------|-------|
| `status` | string | "active" | "all" | Filter by status |

**Response format (JSON):**

**Success (HTTP 200):**

```json
{
  "status": "success",
  "count": 5,
  "users": [
    {
      "phoneNumber": "+12025551234",
      "name": "Alice Johnson",
      "status": "active",
      "createdAt": "2025-01-15T10:30:00Z"
    },
    {
      "phoneNumber": "+13105554567",
      "name": "Bob Smith",
      "status": "active",
      "createdAt": "2025-01-15T10:35:00Z"
    }
  ]
}
```

**Processing logic:**

```
1. Validate operator authentication
2. Query Firebase users collection
   - Filter by status (default "active")
   - Sort alphabetically by name or phone
3. Return results formatted as array
```

**Example curl:**

```bash
curl -X GET "http://localhost:5000/api/users?status=active" \
  -H "Authorization: Bearer operator_token"
```

---

## 6. Health Check Endpoint

### Endpoint: `GET /health`

**Purpose:** Check if backend is running and can connect to Firebase/Twilio

**Triggered by:** Monitoring, Railway health checks

**Request format:**

```
GET /health HTTP/1.1
Host: your-railway-app.railway.app
```

**Response format (JSON):**

**Success (HTTP 200):**

```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T14:30:00.000Z",
  "firebase": "connected",
  "twilio": "configured"
}
```

**Error (HTTP 503):**

```json
{
  "status": "unhealthy",
  "firebase": "disconnected",
  "twilio": "configured"
}
```

---

## Twilio Status Callback (Optional for MVP)

### Endpoint: `POST /twilio/status`

**Purpose:** Receive delivery status updates from Twilio (optional, for future)

**For MVP:** Not implemented, but endpoint can be stubbed

```
POST /twilio/status HTTP/1.1
Host: your-railway-app.railway.app
Content-Type: application/x-www-form-urlencoded

MessageSid=SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
&MessageStatus=delivered
&Timestamp=2025-01-15T14:25:15Z
```

**MVP handling:**
- Just return 200 OK
- Future: Update outgoingMessages document with delivery status

---

## Authentication & Authorization (MVP)

**For MVP, simple approaches:**

**Option 1: API Key in header**
```
Authorization: Bearer <api_key>
```
- Store one hardcoded API key in environment variable
- Backend checks header matches

**Option 2: Session cookies**
- Simple login form on dashboard
- Flask sessions store operator ID in cookie
- All requests validate session exists

**Option 3: No auth (dev mode only)**
- For local testing and Claude Code development
- Add auth before production

**Recommendation:** Option 2 (session-based) is simplest for MVP

---

## Error Codes Summary

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Message sent |
| 400 | Bad request | Invalid phone format |
| 401 | Unauthorized | No valid auth token |
| 403 | Forbidden | User inactive |
| 404 | Not found | User not registered |
| 500 | Server error | Firebase query failed |
| 503 | Service unavailable | Twilio API down |

---

## Rate Limiting (MVP)

**Not needed for MVP** (handful of messages per day)

**Future consideration:**
- Rate limit incoming webhooks from Twilio (to prevent abuse)
- Rate limit API calls from operators (to prevent accidental spam)

---

## Logging & Monitoring

**All endpoints should log:**
- Timestamp
- Method + path
- Status code
- User/operator ID
- Any errors or exceptions

**Example log format:**
```
2025-01-15 14:25:10 [INFO] POST /api/send-message 200 operator_alice
2025-01-15 14:25:11 [INFO] POST /twilio/incoming 200 from:+12025551234
2025-01-15 14:25:12 [ERROR] Firebase write failed: PERMISSION_DENIED
```


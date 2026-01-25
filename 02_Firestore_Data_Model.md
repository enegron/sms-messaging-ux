# Firestore Data Model & Schema Design

## Overview

Firestore is a NoSQL document database. This design uses three main collections to organize data for the SMS messaging system.

---

## Collections & Documents

### Collection 1: `users`

Stores registered user information. Each document represents one user.

**Collection path:** `/users`

**Document ID:** Phone number in E.164 format (e.g., `+12025551234`)

**Firebase Project ID:** `messaging-ux`

**Document schema:**

```
users/{phoneNumber}
├── phoneNumber: string (required)
│   └── E.164 format, e.g., "+12025551234"
├── createdAt: timestamp (required)
│   └── When user was added to system
├── updatedAt: timestamp (required)
│   └── Last time any field was modified
├── status: string (required, enum)
│   └── "active" | "inactive" | "suspended"
│   └── Controls whether user can be messaged
├── name: string (optional)
│   └── User name or label for operator reference
├── metadata: map (optional)
│   └── Custom fields for future use
│   └── Examples: userId, externalId, tags, customField1, etc.
└── notes: string (optional)
    └── Operator notes about this user
```

**Example document:**

```json
{
  "phoneNumber": "+12025551234",
  "createdAt": "2025-01-15T10:30:00Z",
  "updatedAt": "2025-01-15T10:30:00Z",
  "status": "active",
  "name": "Alice Johnson",
  "metadata": {
    "userId": "ext_12345",
    "tags": ["beta", "early-adopter"]
  },
  "notes": "Verified on Jan 15"
}
```

**Indexes:**
- None required for MVP (single document lookups are fast)
- Future: Consider index on `status` if filtering by status becomes common

**Validation rules:**
- `phoneNumber` must be in E.164 format (regex: `^\+[1-9]\d{1,14}$`)
- `status` must be one of: "active", "inactive", "suspended"
- `createdAt` and `updatedAt` must be server timestamps

---

### Collection 2: `incomingMessages`

Logs all incoming SMS messages (from users and unknown numbers).

**Collection path:** `/incomingMessages`

**Document ID:** Auto-generated Firestore ID (timestamp-based)

**Document schema:**

```
incomingMessages/{autoId}
├── timestamp: timestamp (required)
│   └── When message was received by Twilio
├── phoneNumber: string (required)
│   └── E.164 format of sending number
├── messageContent: string (required)
│   └── Full text of SMS (can be empty string)
├── isRegistered: boolean (required)
│   └── true = number is in users collection
│   └── false = number not found in users collection
├── responseSent: boolean (required)
│   └── true = acknowledgment was sent to sender
│   └── false = no response was sent
├── twilio_SmsMessageSid: string (required)
│   └── Twilio's message ID for tracking/debugging
└── notes: string (optional)
    └── Operator notes about this message
```

**Example document:**

```json
{
  "timestamp": "2025-01-15T14:23:45.123Z",
  "phoneNumber": "+12025551234",
  "messageContent": "Hello, testing the system",
  "isRegistered": true,
  "responseSent": true,
  "twilio_SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "notes": ""
}
```

**Indexes:**
- Composite index: (`phoneNumber`, `timestamp` descending) — for querying all messages from a user
- Single field: `timestamp` descending — for querying recent messages
- Single field: `isRegistered` — for filtering registered vs. unknown

**Validation rules:**
- `timestamp` must be server timestamp or near-current time
- `phoneNumber` must be E.164 format
- `isRegistered` must be boolean
- `responseSent` must be boolean
- `messageContent` can be any string, including empty

**Collection size estimate (MVP):**
- Assuming 10 messages per day for 30 days = 300 messages
- Each document ~500 bytes → 150KB storage
- Firestore free tier: 1GB storage = plenty of headroom

---

### Collection 3: `outgoingMessages`

Logs all outgoing SMS messages sent by operators.

**Collection path:** `/outgoingMessages`

**Document ID:** Auto-generated Firestore ID (timestamp-based)

**Document schema:**

```
outgoingMessages/{autoId}
├── queuedAt: timestamp (required)
│   └── When operator initiated send
├── sentAt: timestamp (required)
│   └── When Twilio confirmed message was sent (or null if pending)
├── phoneNumber: string (required)
│   └── E.164 format of recipient
├── messageContent: string (required)
│   └── Full text of SMS sent
├── operatorId: string (required)
│   └── Identifier of operator who sent message
│   └── Could be email, username, or Firestore user ID
├── operatorName: string (optional)
│   └── Display name of operator
├── status: string (required, enum)
│   └── "queued" | "sent" | "failed" | "cancelled"
├── twilio_SmsMessageSid: string (optional)
│   └── Twilio's message ID once sent (null if not yet sent)
├── twilio_ErrorMessage: string (optional)
│   └── Error description if status = "failed"
└── notes: string (optional)
    └── Operator notes about why message was sent
```

**Example document:**

```json
{
  "queuedAt": "2025-01-15T14:25:10.456Z",
  "sentAt": "2025-01-15T14:25:12.789Z",
  "phoneNumber": "+12025551234",
  "messageContent": "Your order has been shipped!",
  "operatorId": "operator_alice",
  "operatorName": "Alice Johnson",
  "status": "sent",
  "twilio_SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "twilio_ErrorMessage": null,
  "notes": "Sent shipping notification"
}
```

**Indexes:**
- Composite index: (`phoneNumber`, `sentAt` descending) — for querying all messages to a user
- Single field: `sentAt` descending — for querying recent messages
- Single field: `status` — for filtering by status
- Single field: `operatorId` — for auditing operator activity

**Validation rules:**
- `queuedAt` must be server timestamp
- `sentAt` must be null (if not yet sent) or a valid timestamp >= `queuedAt`
- `phoneNumber` must be E.164 format and exist in `users` collection
- `status` must be one of: "queued", "sent", "failed", "cancelled"
- `operatorId` must not be empty

**Collection size estimate (MVP):**
- Assuming 5 outgoing messages per day for 30 days = 150 messages
- Each document ~600 bytes → 90KB storage
- Firestore free tier: 1GB storage = plenty of headroom

---

## Relationships & Constraints

### User → Incoming Messages
- Incoming messages reference users via `phoneNumber`
- No foreign key constraint needed in NoSQL, but code must validate before logging

### User → Outgoing Messages
- Outgoing messages reference users via `phoneNumber`
- Backend must validate `phoneNumber` exists in `users` collection before allowing send

---

## Firestore Security Rules

Rules to enforce authorization and data integrity:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    
    // Helper function: Check if user is authenticated
    function isAuthenticated() {
      return request.auth != null;
    }
    
    // Helper function: Check if user is operator (future enhancement)
    // For MVP, we'll use simple auth or environment-based access control
    function isOperator() {
      return isAuthenticated();
    }
    
    // Users collection: Read-only for operators (MVP)
    match /users/{phoneNumber} {
      allow read: if isOperator();
      allow write: if false; // Operators cannot modify via app in MVP
    }
    
    // Incoming messages: Operators can read, backend can write
    match /incomingMessages/{document=**} {
      allow read: if isOperator();
      allow write: if request.auth.uid == "backend-service"; // Backend service account
    }
    
    // Outgoing messages: Operators can read and create, backend can write
    match /outgoingMessages/{document=**} {
      allow read: if isOperator();
      allow create: if isOperator(); // Operators initiate sends
      allow update: if request.auth.uid == "backend-service"; // Backend updates status
      allow delete: if false; // Never delete (audit trail)
    }
  }
}
```

**For MVP development in test mode:**
- Set Firestore to "test mode" during development (allows all reads/writes)
- Before moving to production, switch to "production mode" and implement proper security rules
- Consider using Firebase Admin SDK (service account) for backend operations

---

## Data Migration & Initialization

### Initial user data import (one-time):

```python
# Pseudo-code for importing initial users
users_to_import = [
    {
        "phoneNumber": "+12025551234",
        "name": "Test User 1",
        "status": "active"
    },
    {
        "phoneNumber": "+13105554567",
        "name": "Test User 2",
        "status": "active"
    }
]

for user in users_to_import:
    db.collection('users').document(user['phoneNumber']).set({
        'phoneNumber': user['phoneNumber'],
        'name': user['name'],
        'status': user['status'],
        'createdAt': firestore.SERVER_TIMESTAMP,
        'updatedAt': firestore.SERVER_TIMESTAMP,
        'metadata': {},
        'notes': ''
    })
```

---

## Scaling Considerations for Future

### As message volume grows:

1. **Incoming/Outgoing messages collections** may grow large
   - Firestore handles millions of documents efficiently
   - Consider partitioning by date if queries get slow (e.g., `incomingMessages_2025_01`)
   - Firestore native clustering helps; explicit partitioning is optional

2. **Complex queries** may become necessary
   - MVP uses simple queries (phone number, timestamp)
   - Future: range queries by date, status filtering, operator activity audit
   - Firestore composite indexes support these without code changes

3. **Real-time updates** for campaign management
   - Firestore listeners (Real-time Database features) can trigger backend logic
   - Useful for event-driven messaging in future iterations

4. **Archive old logs**
   - Consider archiving messages older than 90 days to a separate collection
   - Keeps `incomingMessages` and `outgoingMessages` performant for current data

---

## Summary

| Collection | Purpose | Key Fields | Documents/Month (MVP) |
|---|---|---|---|
| `users` | Registered users | phoneNumber, status, createdAt | ~5-10 |
| `incomingMessages` | Incoming SMS logs | phoneNumber, timestamp, messageContent, isRegistered | ~300 |
| `outgoingMessages` | Outgoing SMS logs | phoneNumber, timestamp, messageContent, operatorId | ~150 |

**Total storage (MVP):** ~500KB, well within Firestore free tier (1GB)

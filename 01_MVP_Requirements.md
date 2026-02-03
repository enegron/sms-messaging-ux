# SMS Messaging UX - MVP Requirements Document

## Project Overview

A bidirectional SMS messaging system that enables communication with registered users through text messages. The system handles incoming messages from users, sends outgoing messages from operators, and maintains comprehensive logs of all messaging activity.

**Key Principle:** End-to-end working system demonstrating the core interaction loop, with architecture designed to support future iterations including event-driven messaging, AI agent logic, and campaign management.

---

## MVP Scope

### What's Included in MVP
- User database with phone numbers and basic user metadata
- Incoming SMS message handling (registered and unknown numbers)
- Outgoing SMS message capability (operator-initiated, ad-hoc)
- Comprehensive message logging (incoming and outgoing)
- Operator dashboard/interface to view logs and send messages
- Security controls (only approved users can be messaged)

### What's NOT Included in MVP
- Message delivery/read status tracking
- Proactive event-driven messaging (triggered by external systems)
- Campaign/workflow automation
- AI agent-based message composition
- User signup/onboarding flows
- End-user authentication
- Inbound message parsing/intelligent responses (beyond acknowledgment)

---

## User Stories & Acceptance Criteria

### User Story 1: Registered User Verification
**As a** registered user in the system  
**I want to** send a message to the system's SMS number and receive a confirmation response  
**So that** I can verify I have access to the system

**Acceptance Criteria:**
- When a registered user (phone number in database) sends any message to the system's incoming number, they receive an immediate SMS response
- Response text should be: `"Your number is recognized. Message received."`
- A log entry is created with:
  - Timestamp (date, time, timezone)
  - Sending phone number
  - Message content
  - Status: "Incoming from registered user"
- Response is delivered within 5 seconds of message receipt
- Multiple messages from the same registered user are all acknowledged

---

### User Story 2: Unknown Number Rejection
**As a** system operator  
**I want to** ensure unknown/unregistered phone numbers don't receive responses  
**So that** the system doesn't send messages to unexpected numbers and I can monitor suspicious activity

**Acceptance Criteria:**
- When an unregistered/unknown phone number sends any message to the system's incoming number, NO response is sent to that number
- A log entry is still created with:
  - Timestamp (date, time, timezone)
  - Sending phone number
  - Message content
  - Status: "Incoming from unknown number"
- No error message or bounce-back is sent
- Log entry is stored in persistent storage for monitoring

---

### User Story 3: Operator Incoming Message Log
**As a** system operator  
**I want to** view all incoming messages in one place with full details  
**So that** I can monitor all communication, troubleshoot issues, and detect suspicious activity

**Acceptance Criteria:**
- Dashboard/interface displays all incoming messages (registered and unknown)
- Each log entry shows:
  - Date and time (with timezone)
  - Sending phone number
  - Message content (full text, even if empty)
  - Status (registered user / unknown number)
  - Whether a response was sent
- Logs are sortable by date, phone number
- Logs are searchable by phone number
- Data persists indefinitely
- Only operators with authorization can view logs
- Logs are human-readable and easy to scan

---

### User Story 4: Operator Sends Ad-Hoc Message
**As a** system operator  
**I want to** send a text message to any registered user in the system  
**So that** I can communicate directly with users when needed

**Acceptance Criteria:**
- Operator can access an interface to send a message
- When composing a message:
  - Operator selects from a list of approved/registered phone numbers only
  - No ability to type in arbitrary phone numbers
  - Operator enters message content
  - Operator confirms before sending
- Message is sent via SMS to the selected user
- Sending is only possible to numbers in the registered user database
- Only authorized operators can send messages

---

### User Story 5: Operator Outgoing Message Log
**As a** system operator  
**I want to** view all outgoing messages sent by me or other operators  
**So that** I can verify communication was sent, audit operator activity, and troubleshoot issues

**Acceptance Criteria:**
- Dashboard/interface displays all outgoing messages sent from the system
- Each log entry shows:
  - Date and time (with timezone)
  - Target phone number
  - Message content (full text)
  - Which operator sent it (if tracked)
  - Timestamp when message was queued and when confirmed sent by SMS provider
- Logs are sortable by date, phone number, operator
- Logs are searchable by phone number
- Data persists indefinitely
- Only authorized operators can view logs
- Logs are human-readable and easy to scan

---

## Functional Requirements

### FR1: User Database
- System must maintain a database of registered users
- Each user record includes:
  - Phone number (unique identifier)
  - Created date
  - Last updated date
  - Status (active/inactive)
  - Any additional metadata fields needed
- Database must reliably store and retrieve user information
- Must support at least 2,000 user records

### FR2: Incoming Message Handling
- System must receive incoming SMS messages via Twilio webhook
- For each incoming message:
  - Parse phone number and message content
  - Check if phone number exists in user database
  - If registered: send acknowledgment response, log message
  - If unknown: don't send response, log message anyway
- Message content can be empty, whitespace, or any text

### FR3: Outgoing Message Sending
- System must allow operator to initiate outgoing SMS messages
- Operator must select from a pre-defined list of registered numbers (no free-text entry)
- System must send message via Twilio
- System must only allow sending to registered phone numbers

### FR4: Incoming Message Logging
- All incoming messages must be logged with:
  - Timestamp (UTC or consistent timezone)
  - Sending phone number
  - Message content
  - Registration status (registered/unknown)
  - Response sent (yes/no)
- Logs must be queryable and persistently stored
- Logs must never be deleted (audit trail)

### FR5: Outgoing Message Logging
- All outgoing messages must be logged with:
  - Timestamp when queued (UTC or consistent timezone)
  - Timestamp when confirmed sent by SMS provider (if available)
  - Target phone number
  - Message content
  - Operator who initiated send
- Logs must be queryable and persistently stored
- Logs must never be deleted (audit trail)

### FR6: Operator Authorization
- Only authorized operators can view message logs
- Only authorized operators can send outgoing messages
- System must distinguish between different operators (for audit trail)

### FR7: Operator Authentication
- The web console must be secured via authentication
- The app must NOT use HTTP Basic Authentication
- The operator password must be stored in a persistent datastore accessible by the app (not hardcoded or environment-only)
- The app will present a secure login form over HTTPS
- The app will validate the presented password against the password stored in the secure datastore
- The console (all pages except login) is only accessible after successful authentication
- A session cookie must be used to persist a token representing the authenticated login
- The authenticated session must expire after 4 hours (absolute), requiring re-authentication regardless of activity

### FR8: Phone Number Privacy
- Full phone numbers (PII) must only be stored in one place: the `users` collection
- The phone number must NEVER be used as the value of any field except the user's `phoneNumber` field in `users`
- Message logs (`incomingMessages`, `outgoingMessages`) must NOT contain full phone numbers
- Message logs must reference users by `userId` only (userId is the document ID, which happens to be the phone number, but the phone number value itself is not stored in message fields)
- For incoming messages from unknown/unregistered numbers:
  - Store a SHA256 hash of the phone number (allows correlation without exposing the number)
  - Do not store the actual phone number
  - This is a low-priority use case; minimal resources should be spent on unknown number handling
- When sending outgoing messages, the system looks up the phone number from `users` internally
- The dashboard displays user identifiers (name or masked phone) rather than full phone numbers
- For exposing "masked" phone numbers in the UI (which should be minimized and eventually removed):
  - Phone number must be looked up by userId from `users` collection
  - Masking must be done server-side before returning to UI or logging
- System incoming phone number(s) (Twilio numbers) are stored in configuration/environment variables, not in the persistent datastore
- Twilio API calls use the full phone number as required, but only in memory - never persisted in logs

---

## Non-Functional Requirements

### NFR1: Performance
- Acknowledgment response to registered users: < 5 seconds
- Incoming message logged within 10 seconds of receipt
- Outgoing message sent within 10 seconds of operator initiation
- Dashboard loads within 3 seconds

### NFR2: Availability
- System should be available 24/7 for receiving messages
- Graceful degradation if Twilio or Firebase is temporarily unavailable
- Retry logic for failed message sends (handled by Twilio)

### NFR3: Security & Privacy
- User phone numbers are PII and must be encrypted at rest
- Message logs are sensitive data and must be encrypted at rest
- Operator access must require authentication
- All communication with Twilio and Firebase must use TLS/HTTPS
- Credentials (Twilio API keys, Firebase keys) must never be hardcoded or exposed
- Firebase Firestore rules must enforce authorization

### NFR4: Scalability
- System must handle at least 2,000 registered users
- System must handle at least dozens of messages per day
- Firestore free tier is sufficient for MVP volumes
- Architecture must not require significant refactoring to scale to thousands of messages/day

### NFR5: Auditability
- All message logs must be immutable (append-only)
- All operator actions must be timestamped
- All changes to user database must be auditable

### NFR6: Cost
- MVP must remain in free or near-free tier across all services
- Twilio: free trial ($15 credit, up to 5 verified numbers initially)
- Firebase: free tier Firestore (1GB storage, 50k ops/day)
- Railway: free tier or ~$5/month

---

## Data Flows

### Flow 1: Incoming Message from Registered User
```
1. User sends SMS to system number
2. Twilio receives SMS
3. Twilio forwards to webhook endpoint (via POST)
4. Python backend receives webhook
5. Backend extracts phone number from payload
6. Backend queries Firebase for matching user
7. User found → backend sends acknowledgment SMS via Twilio
8. Backend logs incoming message to Firebase (status: "registered")
9. Backend returns 200 OK to Twilio
```

### Flow 2: Incoming Message from Unknown Number
```
1. Unknown number sends SMS to system number
2. Twilio receives SMS
3. Twilio forwards to webhook endpoint (via POST)
4. Python backend receives webhook
5. Backend extracts phone number from payload
6. Backend queries Firebase for matching user
7. User NOT found → backend sends no response
8. Backend logs incoming message to Firebase (status: "unknown")
9. Backend returns 200 OK to Twilio
```

### Flow 3: Operator Sends Outgoing Message
```
1. Operator opens dashboard
2. Operator selects registered user from list
3. Operator enters message text
4. Operator clicks "Send"
5. Backend receives send request with user ID and message
6. Backend validates operator authorization
7. Backend retrieves user phone number from Firebase
8. Backend sends SMS via Twilio
9. Backend logs outgoing message to Firebase
10. Backend returns success response to dashboard
11. Dashboard shows confirmation to operator
```

### Flow 4: Operator Views Logs
```
1. Operator opens dashboard
2. Operator navigates to Incoming Messages or Outgoing Messages view
3. Dashboard queries Firebase for all messages
4. Dashboard renders table with timestamps, numbers, content, status
5. Operator can filter/search by phone number or date range
6. Operator can view full message content
```

---

## Constraints & Assumptions

- **Phone numbers** are the unique user identifier (E.164 format, e.g., +12025551234)
- **Message content** is plain text SMS (160-1600 characters depending on carrier/content)
- **Timezones**: All timestamps stored in UTC; operator dashboard can display in operator's local timezone
- **Operator count**: MVP assumes small number of operators (< 10), so simple role-based access is sufficient
- **Message volume**: MVP designed for dozens of messages per day, not thousands per second
- **Availability assumption**: Twilio and Firebase are always available (no offline mode required)
- **User signup**: For MVP, users are pre-loaded into database; no self-signup mechanism

---

## Success Criteria for MVP

1. ✅ Registered user sends message → receives acknowledgment within 5 seconds
2. ✅ Unknown number sends message → receives no response
3. ✅ All incoming messages (registered + unknown) appear in operator log within 10 seconds
4. ✅ Operator can send ad-hoc message to any registered user from dashboard
5. ✅ All outgoing messages appear in operator log with full details
6. ✅ Logs are persistent, searchable, and human-readable
7. ✅ System remains in free tier for all services
8. ✅ End-to-end flow works: message in → system processes → message out → logged

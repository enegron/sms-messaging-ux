# SMS Messaging UX - Architecture & System Design

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         SMS Ecosystem                             │
└──────────────────────────────────────────────────────────────────┘

    User/Unknown                                    Operator
    Phone #1          ┌─────────────────────┐       Dashboard
        │             │  Twilio SMS API     │            │
        ├────────────→│  • Incoming Webhook │←───────────┤
        │             │  • Outgoing SMS     │            │
    Phone #2          │  • Phone Number     │       (Browser)
        │             └──────────┬──────────┘            │
        └─────────────────────────┼──────────────────────┘
                                  │ HTTPS
                    ┌─────────────┴──────────────┐
                    │                            │
                ┌───▼────┐              ┌────────▼────┐
                │ Railway │              │   Firebase  │
                │ (Python)│              │  Firestore  │
                │ Backend │              │             │
                └────┬────┘              └────────┬────┘
                     │ SDK                    │ SDK
                     └─────────┬──────────────┘
                               │
                    ┌──────────┴──────────┐
                    │  • users            │
                    │  • incomingMessages │
                    │  • outgoingMessages │
                    └─────────────────────┘
```

---

## Components

### 1. Twilio (SMS Provider)

**Purpose:** Send and receive SMS messages

**Responsibilities:**
- Provides inbound SMS number (free with free trial)
- Receives SMS from users/unknown numbers
- Forwards incoming messages to our backend via webhook
- Sends outgoing SMS on backend request via REST API
- Provides message delivery status and tracking

**Integration points:**
- **Incoming webhook:** Backend listens for POST from Twilio with message details
- **Outgoing API:** Backend makes REST calls to Twilio to send messages

**Credentials needed:**
- Account SID
- Auth Token
- Phone Number (inbound number assigned to your account)

**Cost (MVP):**
- Free trial: $15.50 credit, up to 5 verified phone numbers
- Per message: ~$0.0075 (both incoming and outgoing)
- Inbound number: Free on free trial

---

### 2. Firebase Firestore (Database)

**Purpose:** Persistent storage for users, incoming messages, outgoing messages

**Responsibilities:**
- Store registered user phone numbers and metadata
- Log all incoming SMS (from registered and unknown numbers)
- Log all outgoing SMS sent by operators
- Provide read access to logs for operator dashboard

**Integration points:**
- **Backend:** Python Firebase Admin SDK reads/writes data
- **Dashboard:** Firebase Admin console or custom UI reads data

**Collections:**
- `users` — Registered phone numbers
- `incomingMessages` — Incoming SMS log
- `outgoingMessages` — Outgoing SMS log

**Cost (MVP):**
- Free tier: 1GB storage, 50k read/write/delete operations/day
- MVP estimate: ~500KB storage, <100 operations/day
- Well within free tier

---

### 3. Railway (Python Backend)

**Purpose:** Application logic, orchestration, API endpoints

**Responsibilities:**
- Expose HTTP endpoint for Twilio incoming message webhook
- Parse Twilio webhook payloads
- Query Firebase for user lookup
- Send acknowledgment messages via Twilio for registered users
- Log messages to Firebase (incoming and outgoing)
- Expose API for operator dashboard to initiate outgoing messages
- Validate authorization for outgoing messages
- Handle errors and retries gracefully

**Technology stack:**
- **Framework:** Flask or FastAPI (Python)
- **Database SDK:** Firebase Admin SDK for Python
- **SMS SDK:** Twilio Python library
- **HTTP server:** Gunicorn (production-grade WSGI server)

**Deployment:**
- Git repo (GitHub)
- Connect to Railway
- Railway auto-deploys on git push
- Environment variables: Twilio credentials, Firebase service account key

**Cost (MVP):**
- Free tier: $5/month credit (covers unlimited small services)
- MVP usage: <10 requests/day, well within free tier

---

### 4. Operator Dashboard

**Purpose:** UI for operators to view logs and send messages

**For MVP, two options:**

**Option A: Firebase Admin Console (No custom code)**
- Firebase provides web UI to browse collections
- View users, incoming messages, outgoing messages
- Edit data directly
- **Pros:** Zero code, immediate, simple
- **Cons:** Not user-friendly, exposes Firestore schema directly, limited querying

**Option B: Custom Flask UI (Minimal code)**
- Simple HTML/CSS dashboard served by Railway backend
- View incoming messages (table, sortable, searchable)
- View outgoing messages (table, sortable, searchable)
- Send new message (dropdown for user selection, text input, send button)
- **Pros:** User-friendly, custom UX, operator-focused
- **Cons:** Requires Python code, but minimal HTML/CSS

**Recommendation for MVP:** Start with **Option B (Custom Flask UI)**
- Only ~200-300 lines of HTML/Python code
- Provides better UX than Firebase console
- Easier to hand off to Claude Code with clear requirements
- Provides auth/security baseline for later iterations

**Dashboard screens:**

1. **Login** (simple, for future authentication)
2. **Incoming Messages** (table view of all incoming SMS)
3. **Outgoing Messages** (table view of all sent SMS)
4. **Send Message** (form to compose and send new SMS)
5. **User List** (view all registered users)

---

## Data Flow Diagrams

### Flow 1: Incoming Message from Registered User

```
User Phone                   Twilio              Railway Backend         Firebase
     │                          │                      │                    │
     ├─ SMS sent ──────────────→│                      │                    │
     │                          │                      │                    │
     │                          ├─ POST webhook ──────→│                    │
     │                          │ (phoneNumber,        │                    │
     │                          │  messageContent)     │                    │
     │                          │                      │                    │
     │                          │                      ├─ Query users/ ────→│
     │                          │                      │  {phoneNumber}     │
     │                          │                      │                    │
     │                          │                      │← User found        │
     │                          │                      │  (status: active)  │
     │                          │                      │                    │
     │                          │                      ├─ Create incomingMessages/ ──→│
     │                          │                      │  {phoneNumber,             │
     │                          │                      │   messageContent,          │
     │                          │                      │   isRegistered: true,      │
     │                          │                      │   responseSent: true}      │
     │                          │                      │                           │
     │                          │                      ├─ Send SMS (API call) ────→ Twilio
     │                          │                      │ "Your number is          │
     │                          │                      │  recognized..."           │
     │                          │                      │                           │
     │ ← SMS response ←──────────────────────────────←│                           │
     │  "Your number is                                │                           │
     │   recognized..."          │                      │                    │
```

### Flow 2: Incoming Message from Unknown Number

```
Unknown Phone               Twilio              Railway Backend         Firebase
     │                          │                      │                    │
     ├─ SMS sent ──────────────→│                      │                    │
     │                          │                      │                    │
     │                          ├─ POST webhook ──────→│                    │
     │                          │ (phoneNumber,        │                    │
     │                          │  messageContent)     │                    │
     │                          │                      │                    │
     │                          │                      ├─ Query users/ ────→│
     │                          │                      │  {phoneNumber}     │
     │                          │                      │                    │
     │                          │                      │← User not found    │
     │                          │                      │                    │
     │                          │                      ├─ Create incomingMessages/ ──→│
     │                          │                      │  {phoneNumber,             │
     │                          │                      │   messageContent,          │
     │                          │                      │   isRegistered: false,     │
     │                          │                      │   responseSent: false}     │
     │                          │                      │                           │
     │                          │                      │← Return 200 OK            │
     │                          │← HTTP 200            │ (no SMS response)         │
     │ (No response sent)        │                      │                    │
     │                          │                      │                    │
```

### Flow 3: Operator Sends Outgoing Message

```
Operator Browser         Railway Backend         Twilio              Firebase
     │                          │                  │                    │
     ├─ Click "Send" ──────────→│ POST /send       │                    │
     │ (phoneNumber,             │ {phoneNumber,    │                    │
     │  messageContent)          │  messageContent} │                    │
     │                           │                  │                    │
     │                           ├─ Validate ──────────────────────────→│
     │                           │  operator auth   │ (optional)        │
     │                           │  & phone exists  │                    │
     │                           │                  │                    │
     │                           ├─ Create outgoingMessages/ ────────→│
     │                           │  {phoneNumber,                     │
     │                           │   messageContent,                  │
     │                           │   status: "queued",                │
     │                           │   queuedAt: now}                   │
     │                           │                  │                    │
     │                           ├─ Send via API ──→│                    │
     │                           │ twilio.messages  │                    │
     │                           │ .create(...)     │                    │
     │                           │                  │← SmsMessageSid    │
     │                           │                  │  returned          │
     │                           │                  │                    │
     │                           ├─ Update outgoingMessages/ ──────→│
     │                           │  {status: "sent",                 │
     │                           │   sentAt: now,                    │
     │                           │   twilio_SmsMessageSid}           │
     │                           │                  │                    │
     │← HTTP 200 OK ────────────←│                  │                    │
     │  {status: "sent"}         │                  │                    │
     │                           │                  │                    │
     ├─ Success message shown    │                  │                    │
     │                           │                  │                    │
```

### Flow 4: Operator Views Incoming Messages

```
Operator Browser         Railway Backend         Firebase
     │                          │                    │
     ├─ Load dashboard ────────→│ GET /messages/in    │
     │                          │                    │
     │                          ├─ Query ───────────→│
     │                          │ incomingMessages   │
     │                          │ (all, sorted)      │
     │                          │                    │
     │                          │← Results (docs)    │
     │                          │ [{timestamp,       │
     │                          │   phoneNumber,     │
     │                          │   messageContent,  │
     │                          │   isRegistered}...]│
     │                          │                    │
     │← HTML table ─────────────│                    │
     │ with all messages        │                    │
     │                          │                    │
```

---

## Technology Choices Rationale

| Component | Choice | Why |
|-----------|--------|-----|
| **SMS** | Twilio | Industry standard, excellent API, free trial sufficient, good logging |
| **Database** | Firebase Firestore | Free tier generous, NoSQL fits event-log model, native integration with Python, good for scaling |
| **Backend** | Python + Flask | Simple, fast to develop, excellent Firebase/Twilio libraries, easy to understand |
| **Hosting** | Railway | Zero-friction deployment, free tier, Git integration, environment variable management |
| **Dashboard** | Custom Flask UI | Minimal code, operator-friendly, full control over UX |

---

## Security Architecture

### Authentication & Authorization

**MVP approach:**
- Simple environment variable or hardcoded operator credentials
- Flask session/cookie-based auth
- Future: Firebase Authentication + role-based access

**Data security:**
- All credentials stored in Railway environment variables (not in code)
- Firebase service account key in environment variables
- Firestore security rules enforce authorization at database level
- TLS/HTTPS for all external communication (Twilio API, Firebase)

### PII Handling

- User phone numbers are PII
- Firebase encrypts at rest
- Backend must never log unmasked phone numbers to stdout or other outputs
- Unmasked numbers can only be used when critical to make a API calls to act on the number, and then must over secure endpoints
- Operator dashboard requires authentication, but should never reveal unmaked numbers

### Audit Trail

- All incoming messages logged with timestamp
- All outgoing messages logged with operator ID and timestamp
- Logs are immutable (no deletion in security rules)
- Can reconstruct all communication history

---

## Error Handling & Resilience

### Twilio webhook failures

**Scenario:** Backend fails to process incoming message from Twilio

**Handling:**
- Return non-200 status to Twilio
- Twilio retries webhook delivery up to 3 times (configurable)
- If all retries fail, message is logged in Twilio console
- Operator can review Twilio logs and manually process if needed

### Firebase write failures

**Scenario:** Backend can't write log to Firebase

**Handling:**
- Catch exception in backend
- Log error locally (to stdout/logs)
- Return error response to Twilio/operator
- Operator should review logs to see what went wrong

### Twilio send failures

**Scenario:** Backend tries to send SMS but Twilio returns error

**Handling:**
- Catch exception from Twilio SDK
- Log error to Firebase with status="failed"
- Return error to operator dashboard
- Operator can retry or investigate

### Rate limiting & quotas

**MVP volumes:**
- Twilio free tier: $15.50 credit = ~2,000 SMS
- Firebase: 50k operations/day = plenty
- Railway: Unlimited requests on free tier
- No rate limiting needed for MVP

---

## Scaling Path (Future)

### Architecture remains same, but:

1. **Message volume growth**
   - Firestore handles millions of documents
   - Twilio scales transparently
   - Railway can scale to multiple instances (no code changes)

2. **Event-driven messaging** (roadmap)
   - Add event listeners to Firestore
   - Trigger outgoing messages based on user state changes
   - Queue messages in a separate collection
   - Background worker processes queue

3. **AI agent integration** (roadmap)
   - Add LLM API calls (OpenAI, Anthropic, etc.)
   - Agent reads user state and campaign rules
   - Agent composes messages
   - Backend sends via Twilio as before

4. **Analytics & dashboards**
   - Firestore can handle query aggregations
   - Future: Add data warehouse (BigQuery) for complex analytics

---

## Deployment Checklist

### Before going live:
- [ ] Twilio account set up with inbound number
- [ ] Firebase project created with Firestore database
- [ ] Users loaded into Firebase
- [ ] Python backend deployed to Railway
- [ ] Twilio webhook URL configured and tested
- [ ] Operator dashboard working
- [ ] Send/receive test messages end-to-end
- [ ] Logs appearing in Firebase
- [ ] Operator can view all logs and send messages
- [ ] Security rules applied to Firestore

---

## Success Metrics

| Metric | Target | How to measure |
|--------|--------|-----------------|
| **Message latency** | <5s acknowledgment | Timestamp in log vs. sent time |
| **Log persistence** | 100% | All sent/received messages appear in logs |
| **Dashboard availability** | 99%+ | Manual testing, uptime monitoring |
| **Cost** | <$5/month | Track Twilio, Firebase, Railway usage |
| **Operator efficiency** | <2min to send message | Time from dashboard load to send confirmation |


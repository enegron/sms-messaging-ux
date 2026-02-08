# Product Roadmap & Future Architecture Considerations

## Overview

This document outlines the product vision beyond MVP and how the MVP architecture supports future iterations. The goal is to show that the foundation we're building is flexible enough to scale toward an AI-agent-driven, event-triggered messaging platform while maintaining core simplicity.

---

## MVP → Future State Vision

### MVP (Current)
- **User interaction:** Bidirectional ad-hoc messages only
- **Operator control:** Manual message sending
- **Message flow:** User → System → Operator (reactive)
- **Scope:** 2,000 users, dozens of messages/day

### Iteration 2: Event-Driven Messaging
- **New capability:** System sends proactive messages based on external events
- **Examples:** Order shipped, account created, payment received
- **Architecture change:** Add event listeners, message queue

### Iteration 3: AI Agent Integration 
- **New capability:** AI agent composes messages and makes decisions dynamically
- **Examples:** Agent reads user state, past messages, generates contextual responses
- **Architecture change:** LLM API integration, agent orchestration

---

## Iteration 2: Event-Driven Messaging

### Goals
- Enable proactive messaging triggered by external systems
- Maintain MVP simplicity for basic ad-hoc messaging

### New Requirements

**User Story 1: System Sends Message on External Event**

As the system operator, I want to trigger SMS messages based on events from external systems (e.g., shipping, payment) so that users receive timely notifications without manual intervention.

**Acceptance Criteria:**
- System can receive events from external systems (webhook or API)
- Operator can define simple "if X happens, send Y message" rules
- Messages are sent automatically when events occur
- All outgoing messages still logged with event source

**User Story 2: Message Queue & Scheduling**

As the system operator, I want messages to be queued and delivered at appropriate times so that users don't receive messages at inappropriate times of the day

**Acceptance Criteria:**
- Messages can be scheduled for future delivery
- System respects quiet hours (e.g., 10 PM - 8 AM)
- Messages in queue can be cancelled before sending
- Queue status visible in operator dashboard

### Architectural Changes

**New collections:**
- `events` — External events that trigger messages
- `outGoingMessageQueue` — Messages waiting to be sent

**New services:**
- Event listener service (listens to external systems)
- Message queue processor (dequeues and sends messages)
- Scheduler service (handles time-based delays)

**Diagram:**

```
External Systems             Event Listener         Message Queue        Twilio
(Shopify, etc.)                │                        │                 │
        │                      │                        │                 │
        ├─ Order shipped ─────→│ Event received         │                 │
        │                      │ Write to events/ ───→─┐│                 │
        │                      │                        ││                 │
        │                      │                        ├─ Check rules     │
        │                      │                        │  Create message  │
        │                      │                        │  in queue        │
        │                      │                        │                  │
        │                      │                        │ Processor runs   │
        │                      │                        │ every 5 min      │
        │                      │                        ├─ Dequeue msg    │
        │                      │                        │  Check time OK   │
        │                      │                        ├──────────────────→
        │                      │                        │  Send via Twilio │
        │                      │                        │                  │
        │                      │                        │← Delivery status │
        │                      │                        └──────────────────┘
```

### Implementation Notes

**Technology choices:**
- **Event listener:** Cloud Functions (Firebase) or Celery tasks (Python)
- **Message queue:** Firestore collection or Redis (if using Celery)
- **Scheduler:** Cloud Scheduler (Firebase) or APScheduler (Python)

**MVP compatibility:**
- Operator can still send ad-hoc messages (unchanged)
- Event-driven messages appear in same outgoing logs
- No breaking changes to existing endpoints

**Cost considerations:**
- Firebase Cloud Functions: 2M invocations/month free
- Firestore: Already in use, minimal additional cost
- Total: Still free tier

---

## Long-Term Vision

### Advanced Features

**Conversational AI:**
- User sends message → Agent understands intent → Responds naturally
- Learn user preferences and tone from history
- Handle complex requests (account status, order tracking, etc.)

**Multi-channel expansion:**
- RCS, WhatsApp, Telegram, Facebook Messenger in addition to SMS
- Each channel has different constraints (SMS = 160 chars, others = unlimited)
- Agent adjusts message format per channel

**Analytics & Insights:**
- Dashboard showing engagement metrics
- Cohort analysis (which messages work for which user segments?)
- ML models predicting user behavior

---

## MVP Foundation → Future State Compatibility

### Design Decisions That Enable Scaling

| Design Decision | Why It Matters | Supports Future |
|---|---|---|
| **Firestore (not SQL)** | Easy to add new fields/collections | ✓ Agent data |
| **Event-driven architecture** | Messages triggered by events | ✓ Event listeners, LLM |
| **Stateless backend** | Easy to scale horizontally | ✓ High-volume message processing |
| **Separate logs collections** | Immutable audit trail | ✓ Agent reasoning logs, compliance |
| **Operator dashboard** | UI patterns reusable | ✓ agent reasoning viewer |
| **Twilio abstraction** | Easy to add new channels | ✓ Multi-channel support |
| **Python backend** | Excellent ML/LLM libraries | ✓ LLM integration, analytics |
| **Environment-based config** | Secrets not in code | ✓ API keys for new integrations |

### What NOT to Change

These MVP patterns should remain consistent through future iterations:

1. **User identifier:** Phone number (E.164) — foundation of everything
2. **Message log format:** Same incoming/outgoing structure
3. **Twilio integration:** Core abstraction for SMS
4. **Firebase collections:** Can add new collections, but don't rename existing
5. **Operator dashboard:** Add features, but maintain UX patterns

---

## Success Metrics for Roadmap

| Phase | Key Metric | Target |
|-------|-----------|--------|
| **MVP** | E2E message working | 100% ✓ |
| **Event-Driven** | % messages auto-sent | 50%+ |
| **AI Agent** | Message relevance (human rating) | 4/5 stars |
| **Advanced** | User engagement rate | 40%+ |

---

## Conclusion

The MVP is intentionally scoped to be simple and testable. But every architectural decision is made with future iterations in mind:

- **Firestore** instead of SQL allows flexible data evolution
- **Stateless backend** scales to thousands of messages/day
- **Event-driven design** supports both manual and automated messaging
- **Clean separation** of concerns (Twilio ↔ Backend ↔ Firebase ↔ Dashboard) allows swapping components
- **Python + Flask** provides excellent foundation for LLM integration

By Month 4-5, we'll have an **AI-agent-driven SMS platform** capable of sophisticated, context-aware messaging at scale. The MVP foundation makes this evolution smooth, not a rebuild.

---

## Backlog

### Consider Migrating to Render

**Status:** Future consideration

Deployment is currently on Railway Free tier which has limitations:
- Serverless deployments (app sleeps after inactivity, cold start delay on first request)
- 1 vCPU / 0.5 GB RAM per service
- Random region assignment (no region selection)
- Potential timeout issues with Twilio webhooks if app is sleeping during incoming SMS

Consider migrating to Render for reduced friction and more predictable free tier behavior.

---

### ~~Phone Number Masking in UI~~ ✅ COMPLETED

**Status:** Implemented in FR8 (Phone Number Privacy)

Phone numbers are now masked in the UI (e.g., `***-***-6377`). Implementation:
- `mask_phone_number()` utility in `services/firebase.py`
- Applied at API response serialization level
- Message logs store `userId` instead of phone numbers
- Unknown numbers stored as SHA256 hash (`unknown_xxxx`)


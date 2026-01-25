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

### Iteration 2: Event-Driven Messaging (Months 2-3)
- **New capability:** System sends proactive messages based on external events
- **Examples:** Order shipped, account created, payment received
- **Architecture change:** Add event listeners, message queue
- **Scope:** Same 2,000 users, hundreds of messages/day

### Iteration 3: Campaign Management (Months 3-4)
- **New capability:** Define message sequences (campaigns) triggered by user state
- **Examples:** Onboarding flow (5 messages over 7 days), re-engagement (3 messages over 2 weeks)
- **Architecture change:** Add campaign engine, user state machine, scheduling
- **Scope:** 10,000 users, thousands of messages/day

### Iteration 4: AI Agent Integration (Months 4+)
- **New capability:** AI agent composes messages and makes decisions dynamically
- **Examples:** Agent reads user state, past messages, campaign rules, generates contextual responses
- **Architecture change:** LLM API integration, agent orchestration
- **Scope:** 100,000 users, advanced personalization

---

## Iteration 2: Event-Driven Messaging (3-month roadmap)

### Goals
- Enable proactive messaging triggered by external systems
- Maintain MVP simplicity for basic ad-hoc messaging
- Lay groundwork for campaign automation

### New Requirements

**User Story 1: System Sends Message on External Event**

As the system operator, I want to trigger SMS messages based on events from external systems (e.g., shipping, payment) so that users receive timely notifications without manual intervention.

**Acceptance Criteria:**
- System can receive events from external systems (webhook or API)
- Operator can define simple "if X happens, send Y message" rules
- Messages are sent automatically when events occur
- All outgoing messages still logged with event source

**User Story 2: Message Queue & Scheduling**

As the system operator, I want messages to be queued and delivered at appropriate times so that users don't receive messages at 3 AM.

**Acceptance Criteria:**
- Messages can be scheduled for future delivery
- System respects quiet hours (e.g., 10 PM - 8 AM)
- Messages in queue can be cancelled before sending
- Queue status visible in operator dashboard

**User Story 3: Delivery & Read Status Tracking**

As the system operator, I want to see if messages were delivered and read so that I can measure engagement.

**Acceptance Criteria:**
- Track SMS delivery status from Twilio
- Track if user opened/read message (via click tracking or interactive response)
- Dashboard shows delivery/read metrics per message
- Delivery status updates in real-time

### Architectural Changes

**New collections:**
- `events` — External events that trigger messages
- `messageQueue` — Messages waiting to be sent
- `campaigns` — Message sequences

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

## Iteration 3: Campaign Management (Month 3-4)

### Goals
- Define reusable message sequences
- Automate multi-step user journeys
- Track user progress through campaigns

### New Requirements

**User Story 1: Create Campaign Template**

As the operator, I want to define a series of messages to be sent to users over time based on triggering event, so I can automate common workflows.

**Example campaign:**
```
Name: "Order Fulfillment"
Trigger: "Order placed" (event from Shopify)
Messages:
  1. Day 0: "Thanks for your order! You'll get updates as we process it."
  2. Day 1: "Your order has shipped! Track it here: [link]"
  3. Day 3: "Delivery in progress. Expect it tomorrow."
  4. Day 5: "Did your order arrive? Let us know!"
```

**Acceptance Criteria:**
- Operator can create campaign with message sequence
- Each message in sequence has: content, delay (days/hours), conditional rules
- Campaigns can be enabled/disabled
- Active campaigns shown in dashboard

**User Story 2: Enroll Users in Campaign**

As the system, I want to automatically enroll users in appropriate campaigns based on events, so they receive the right message sequence.

**Acceptance Criteria:**
- When trigger event occurs for a user, user is enrolled in campaign
- User receives messages in sequence at correct times
- User can only be in one instance of each campaign (no duplicates)
- Operator can manually enroll users

**User Story 3: Track Campaign Metrics**

As the operator, I want to see how users progress through campaigns, so I can measure effectiveness.

**Acceptance Criteria:**
- Dashboard shows: enrollment count, message send rate, delivery rate, engagement metrics
- Can drill down to see individual users in campaign
- Can see if user completed campaign or dropped out

### Architectural Changes

**New collections:**
- `campaigns` — Campaign definitions
- `campaignEnrollments` — User enrollment in campaigns
- `campaignMetrics` — Aggregated analytics

**New logic:**
- Campaign enrollment trigger (when event matches)
- Campaign progress tracking (user state in campaign)
- Campaign analytics aggregation

**Diagram:**

```
User Event              Campaign Engine           Message Queue        Twilio
     │                       │                        │                 │
     ├─ User placed order ──→│ Check active campaigns  │                 │
     │                       │ Order Fulfillment       │                 │
     │                       │ triggered ──────────→  │                 │
     │                       │                        │ Queue all msgs   │
     │                       │                        │ in campaign      │
     │                       │                        │                  │
     │                       │ Record enrollment ────→│ Dequeue per      │
     │                       │ in campaignEnrollments  │ schedule         │
     │                       │                        ├─────────────────→│
     │                       │                        │  Send message    │
     │                       │                        │                  │
     │                       │ (Day 1) ────────────→  │← Status update   │
     │                       │ Check progress         │ Update           │
     │                       │ Send next message      │ enrollments      │
     │                       │                        ├──────────────────→
     │                       │                        │  Send message 2  │
     │                       │                        │                  │
```

### Implementation Notes

**New endpoints:**
- `POST /api/campaigns` — Create campaign
- `GET /api/campaigns` — List campaigns
- `POST /api/users/{id}/campaigns/{campaignId}/enroll` — Manually enroll user
- `GET /api/campaigns/{id}/metrics` — Campaign analytics

**Campaign definition format:**
```json
{
  "id": "camp_order_fulfillment",
  "name": "Order Fulfillment",
  "description": "Post-purchase email sequence",
  "trigger": {
    "type": "event",
    "event_type": "order.placed",
    "source": "shopify"
  },
  "enabled": true,
  "messages": [
    {
      "sequence": 1,
      "delay_hours": 0,
      "content": "Thanks for your order!",
      "conditions": [
        {
          "type": "user_status",
          "operator": "equals",
          "value": "active"
        }
      ]
    },
    {
      "sequence": 2,
      "delay_hours": 24,
      "content": "Your order has shipped!",
      "conditions": []
    }
  ]
}
```

**Cost:**
- Minimal additional Firestore usage
- Possible upgrade to Cloud Scheduler if needed (still free tier)

---

## Iteration 4: AI Agent Integration (Month 4+)

### Goals
- Empower agent to compose messages dynamically
- Make smart decisions about when/what to send
- Personalize based on user history

### Vision

Instead of pre-written campaigns, provide the agent with:
- User state and history
- Campaign intent in natural language
- Rules and constraints
- LLM + tools for decision-making

**Example:**
```
Campaign rule (in English):
"Send a message to users who placed an order 3 days ago 
but haven't received their tracking number yet. 
The message should apologize for the delay, explain what's happening,
and provide an estimated timeline. Keep it under 160 characters 
so it fits in one SMS."

Agent:
1. Reads user state: order_date = 3 days ago, tracking_status = null
2. Checks rule: conditions match ✓
3. Composes message: "Sorry for the delay! We're processing your order now. 
   You'll get tracking info by tomorrow. Thanks for your patience!"
4. Validates: <160 chars ✓
5. Sends message
6. Logs reasoning for audit trail
```

### New Requirements

**User Story 1: Define Campaign Rules in Natural Language**

As the operator, I want to describe campaign logic in simple English rather than complex UI rules, so I can build sophisticated workflows without technical help.

**Example rules:**
- "Send welcome message when new user enrolls, unless they've received marketing emails in the past 24 hours"
- "If user replies to message with 'help', send FAQ and mark for human review"
- "Delay shipping notification by 1 hour if it's after 9 PM in user's timezone"

**User Story 2: AI Agent Composes Messages**

As the system, I want to use AI to generate contextual, personalized messages based on user data and campaign intent, so messages feel natural and relevant.

**Example:**
- Campaign: "Order delay notification"
- Agent reads: user_name, order_date, estimated_arrival, previous_messages
- Agent writes: "[Name], your order is delayed. New arrival: [date]. Updates at [link]."

**User Story 3: Agent Decision-Making**

As the system, I want the agent to decide whether to send messages and when, based on complex rules and context, so we avoid message fatigue.

**Example decisions:**
- "User already got 3 messages this week → skip for now"
- "User is in quiet hours (11 PM) → schedule for 8 AM"
- "User replied recently → adjust tone to be more conversational"

### Architectural Changes

**New services:**
- **LLM service** — Calls to OpenAI/Anthropic API
- **Agent orchestrator** — Coordinates agent reasoning
- **Tool library** — Agent tools (read user state, send message, etc.)

**New collections:**
- `agentRules` — Campaign rules in natural language
- `agentReasoning` — Agent decision logs (for audit trail)

**New integrations:**
- OpenAI API (or Claude API via Anthropic)
- Tool definitions for agent use

**Diagram:**

```
Campaign Rule                LLM Agent                 Tools                Database
(in English)                    │                       │                      │
      │                         │                       │                      │
      ├─ "Send message ────────→│                       │                      │
      │  if order placed        │                       │                      │
      │  3+ days ago"           │ Reason: analyze       │                      │
      │                         │ user state ──────────→│ Read user/  ────────→│
      │                         │ What conditions?      │ order data  ←────────│
      │                         │                       │                      │
      │                         │ Check if user  ──────→│ Query logs  ────────→│
      │                         │ already messaged      │ Messages in  ←───────│
      │                         │ this week?            │ past 7 days         │
      │                         │                       │                      │
      │                         │ Compose message ──────→│ Create draft────────→│
      │                         │ "Hey, order delayed   │ in temp storage      │
      │                         │ by [X days], new ETA  │                      │
      │                         │ [date]. Track here."  │                      │
      │                         │                       │                      │
      │                         │ Decide: send now ─────→│ Queue message ──────→│
      │                         │ or delay?             │ Schedule for 8 AM    │
      │                         │ (avoid quiet hours)   │                      │
      │                         │                       │                      │
      │                         │ Log reasoning  ──────→│ Record in ──────────→│
      │                         │ (audit trail)         │ agentReasoning       │
      │                         │                       │                      │
```

### Implementation Notes

**LLM prompting strategy:**
```
System prompt:
"You are an SMS marketing assistant. Your job is to:
1. Analyze user state and campaign rules
2. Decide whether to send a message (YES/NO)
3. If YES, compose a personalized SMS (max 160 chars)
4. Provide reasoning for your decision

You have access to:
- User data (name, order history, timezone)
- Campaign intent
- Rules (conditions, constraints)
- User message history
- Current time/date

Format your response as JSON:
{
  'decision': 'SEND' | 'SKIP',
  'message': 'String, if SEND',
  'reasoning': 'String explaining decision',
  'delay_until': 'ISO timestamp, if scheduled',
  'confidence': 0.0-1.0
}
"
```

**Agent tools (via function calling):**
```
Tools available to agent:
- read_user(user_id) → user object
- read_order(order_id) → order object
- read_recent_messages(user_id, days=7) → list of messages
- get_current_time() → ISO timestamp
- schedule_message(user_id, message, delay_hours) → scheduled_id
```

**Cost:**
- OpenAI API: ~$0.001 per message composition ($0.01 for GPT-4 Turbo)
- For 1,000 users, 2 messages/week = 4,000 agent calls/month ≈ $40/month
- Alternative: Use Claude API (similar pricing)

**Future optimization:**
- Cache agent reasoning for similar users
- Batch agent calls
- Use cheaper model (GPT-3.5) for simple rules

---

## Long-Term Vision (6+ months)

### Advanced Features

**Conversational AI:**
- User sends message → Agent understands intent → Responds naturally
- Learn user preferences and tone from history
- Handle complex requests (account status, order tracking, etc.)

**Multi-channel expansion:**
- WhatsApp, Telegram, Facebook Messenger in addition to SMS
- Each channel has different constraints (SMS = 160 chars, others = unlimited)
- Agent adjusts message format per channel

**Analytics & Insights:**
- Dashboard showing engagement metrics
- A/B testing campaigns
- Cohort analysis (which messages work for which user segments?)
- ML models predicting user behavior

**Integration marketplace:**
- Pre-built integrations with Shopify, Stripe, etc.
- Operators can easily connect data sources
- Agent accesses real-time business data

---

## MVP Foundation → Future State Compatibility

### Design Decisions That Enable Scaling

| Design Decision | Why It Matters | Supports Future |
|---|---|---|
| **Firestore (not SQL)** | Easy to add new fields/collections | ✓ Agent data, campaign metadata |
| **Event-driven architecture** | Messages triggered by events | ✓ Event listeners, campaigns, LLM |
| **Stateless backend** | Easy to scale horizontally | ✓ High-volume message processing |
| **Separate logs collections** | Immutable audit trail | ✓ Agent reasoning logs, compliance |
| **Operator dashboard** | UI patterns reusable | ✓ Campaign UI, agent reasoning viewer |
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

## Roadmap Timeline (Estimate)

| Phase | Timeline | Focus | Complexity |
|-------|----------|-------|-----------|
| **MVP** | Now → Month 1 | Basic bidirectional SMS | Low |
| **Event-Driven** | Month 2-3 | Proactive messages, queue | Medium |
| **Campaigns** | Month 3-4 | Multi-message sequences | Medium |
| **AI Agent** | Month 4-5 | LLM integration, dynamic composition | High |
| **Advanced** | Month 6+ | Multi-channel, analytics, integrations | Very High |

---

## Success Metrics for Roadmap

| Phase | Key Metric | Target |
|-------|-----------|--------|
| **MVP** | E2E message working | 100% ✓ |
| **Event-Driven** | % messages auto-sent | 50%+ |
| **Campaigns** | Avg campaign completion rate | 70%+ |
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


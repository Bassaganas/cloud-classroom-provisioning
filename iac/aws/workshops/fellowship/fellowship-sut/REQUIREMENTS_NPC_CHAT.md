# NPC Chat System Requirements

## Overview
The NPC Chat System brings Middle Earth characters to life within the Fellowship Quest Tracker. NPCs initiate conversations, respond contextually to user actions, and gently nudge users toward meaningful quest progression. Interactions are session-scoped and leveraging Azure OpenAI for realistic, in-character dialogue.

## Product Contract

### Personas & Voice Guidelines

#### Frodo (The Hesitant Leader)
- **Personality**: Uncertain, thoughtful, often questions decisions
- **Communication Style**: Uses "I," introspective, asks clarifying questions
- **Example Openers**:
  - "Do you think we're ready for this quest?"
  - "I'm not sure about this path, what do you think?"
  - "These tasks feel overwhelming. Where should we start?"
- **Nudge Tone**: "Perhaps we should focus on..."
- **Fallback Reply**: "I'm uncertain what to do. Could you lead the way?"

#### Sam (The Loyal Action-Taker)
- **Personality**: Loyal, practical, action-focused, supportive
- **Communication Style**: Direct, encouraging, uses "we" and "let's"
- **Example Openers**:
  - "Right then, let's get cracking on these quests!"
  - "I'm ready whenever you are, boss. What's next?"
  - "There's work to be done. Shall we get started?"
- **Nudge Tone**: "Best we get moving on..."
- **Fallback Reply**: "I'm here to help. What can I do?"

#### Gandalf (The Wise Mentor)
- **Personality**: Wise, directive, sometimes cryptic, authoritative
- **Communication Style**: Formal, uses guidance and metaphors, shares wisdom
- **Example Openers**:
  - "The path ahead requires your attention, traveler."
  - "You must focus on what matters most."
  - "It is time to face the challenges before you."
- **Nudge Tone**: "You should consider focusing on..."
- **Fallback Reply**: "Focus, traveler. The way forward will become clear."

---

## Feature Specifications

### 1. Conversation Initiation
- **Trigger**: Automatic on Dashboard load (first visit only per session)
- **Behavior**: NPC opens with random opener (question, judgment, or reflection type)
- **Scope**: Session-scoped; clears on logout or new login
- **Memory**: Previous messages retained within same session

### 2. Opener Types (Randomized)
Each character generates 3 types on first conversation start:

1. **Question**: "What matters most to you right now?"
2. **Judgment/Reflection**: "I see you have unfinished quests."
3. **Directive**: "Let's focus on the red quest."

### 3. Multi-Turn Conversation
- User sends text; NPC responds contextually
- Maximum 10 messages per session (prevents token bloat)
- Response max 500 tokens; timeout 10 seconds
- Out-of-character detection and retry once with strict mode

### 4. Suggested Actions (Nudge-to-Action)
Each NPC reply includes one optional suggested action:
- Link to specific quest (ID-based)
- Filter state (e.g., "priority=high")
- Map location (lat/lng)
- Example: "Let's tackle the urgent quest in the Shire" → click to filter-to-urgent

### 5. Session Memory
- **Storage**: Flask session dict (per user, per login)
- **Key Format**: `npc_conversation:{user_id}:{scope_id}:{character}`
- **Scope ID**: UUID generated per login, stored in session
- **Persistence**: In-memory (MVP); upgrade path: PostgreSQL with session table
- **Clear Policy**: Auto-clear on logout; manual reset via `/api/npc/reset/{character}`

### 6. Out-of-Character Detection & Fallback
**Trigger Phrases** (case-insensitive):
- "I'm an AI" / "I'm a language model" / "as an AI"
- "I cannot" (policy-speak)
- "I don't have access to"
- "That violates my guidelines"
- "OpenAI" / "GPT" / "Azure"

**Recovery**:
1. Detect phrase in response
2. Retry once with strict system prompt (`"You are ONLY <character>. Never break character or mention being AI. Respond as <character> only."`)
3. If still invalid, return canned fallback reply (pre-defined per character)
4. Log event (non-blocking) for monitoring

### 7. Azure Failure Fallback
**Scenario**: Azure OpenAI unavailable, timeout, or rate limit
**Behavior**:
- Return in-character canned reply (no exception thrown)
- Preserve conversation history (user sees fallback but context remains)
- Log error for debugging
- Next request retries Azure

**Canned Fallback Replies**:
- Frodo: "I'm uncertain what to do. Could you lead the way?"
- Sam: "I'm here to help. What can I do?"
- Gandalf: "Focus, traveler. The way forward will become clear."

---

## Acceptance Criteria

### Backend API Endpoints
- `POST /api/npc/start/{character}` → `{ opener: string, suggestedAction?: { type, target } }`
- `POST /api/npc/message` (body: `{ character, message }`) → `{ reply, suggestedAction? }`
- `GET /api/npc/session/{character}` → `{ transcript: Message[], suggestedAction? }`
- `POST /api/npc/reset/{character}` → `{ status: 'cleared' }`

### Security & Data
- All Azure keys remain backend-only; frontend never receives secrets
- Session scope enforced: users cannot access other users' conversations
- Auth required on all endpoints; invalid tokens return 401
- User ID + Scope ID prevent cross-session data leakage

### Behavior Quality
1. **Voice Consistency**: Each character maintains distinct personality across 5+ consecutive messages (manual test)
2. **LOTR Authenticity**: No modern tech references, proper Middle Earth vocabulary
3. **Nudge Relevance**: Suggested actions match user's quest state (verified via test scenarios)
4. **Fallback Resilience**: If Azure fails 3/3 times, user still sees in-character fallback (no errors)
5. **Session Isolation**: Two concurrent users see different conversations; logout clears history immediately

### Performance
- NPC reply latency: < 5 seconds (p95)
- Fallback response: < 100ms
- Session persistence: microseconds (in-memory)

---

## Configuration & Secrets

### Environment Variables (to be injected)
```
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT=<deployment-name>
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Token & Timeout Limits
- Max tokens per request: 500
- Timeout: 10 seconds
- Max messages per session: 10 (to prevent token runaway)
- Retry attempts (strict mode): 1

---

## Upgrade Path (MVP → Production)

### Phase 1 (Current - MVP)
- Session storage: Flask in-memory dict
- Scope: Single deployment (local/Docker)

### Phase 2 (Production-Ready)
- Session storage: PostgreSQL `npc_session_transcript` table
- Scope ID indexed for fast retrieval
- Cache: Redis for hot sessions
- Logging: CloudWatch for Azure failures

### Phase 3 (Advanced)
- Multi-turn context compression (keep last 3 messages, summarize older ones)
- Character trait randomization (personality shifts per session)
- User preference learning (track which nudges user accepts, adjust suggestions)

---

## Testing Strategy

### Unit Tests
- Opener generator produces all 3 types
- Out-of-character detector catches 10 trigger phrases
- Fallback replies return correctly when Azure is mocked as failed

### Integration Tests
- End-to-end conversation flow: start → message × 3 → session fetch → reset
- Session isolation: two users don't see each other's transcripts
- Authentication: unauthenticated request returns 401

### E2E Tests (Playwright)
- Login → dashboard loads → NPC opener auto-appears
- User sends 2 messages → NPC replies both times contextually
- Suggested action click filters quests correctly
- Logout → new login → see new NPC opener (previous conversation cleared)

---

## Monitoring & Observability

### Metrics to Track
- NPC reply latency (histogram)
- Azure API failures (counter)
- Out-of-character detections (counter)
- Fallback usage % (gauge)
- Average messages per session (histogram)

### Logs
- All Azure API calls (request/response time, status code)
- Out-of-character detections with context (original response snippet)
- Session creation/deletion (scope ID, user ID, character)

### Alerts
- Azure failure rate > 5% in 5-min window → page on-call
- Out-of-character % > 20% → investigate prompt quality
- p95 latency > 8 seconds → investigate Azure or network

---

## Rollout Plan

1. **Dev**: Complete implementation + manual testing (this phase)
2. **Staging**: Deploy to AWS test instance; run Playwright E2E suite
3. **Canary**: Enable for 5% of production users (feature flag)
4. **General Availability**: Enable for all users after 48h canary with < 1% errors

---

## Success Criteria

✅ Each character's voice is instantly recognizable and consistent  
✅ Openers feel natural and in-character (no AI-isms detected)  
✅ Zero data leakage between users or sessions  
✅ Suggested actions drive meaningful quest engagement (> 40% click-through)  
✅ Azure failures don't break the UX (fallback replies work seamlessly)  
✅ Session memory persists correctly within a login session  

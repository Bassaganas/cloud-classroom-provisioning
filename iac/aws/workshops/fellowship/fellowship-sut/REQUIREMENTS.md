# Fellowship SUT - Requirements Addendum (Azure NPC Chat)

## Scope
This document defines product and technical requirements for realistic NPC chat with LOTR main characters powered by Azure AI.

## Product Requirements

### R1 - Realistic in-character conversation
- The user can choose Frodo, Sam, or Gandalf.
- NPC responses must remain in-character and context-aware.
- NPC must avoid generic assistant wording and maintain Middle-earth framing.

### R2 - NPC initiates conversation
- On new conversation start, NPC opens with a random style:
  - question,
  - judgement,
  - reflection.
- Openers must differ across sessions and characters.

### R3 - Multi-turn chat
- User can continue chatting in a normal message loop.
- Chat keeps per-login-session memory for MVP.
- User can reset conversation and get a fresh opener.

### R4 - Action-oriented guidance
- NPC always nudges the user toward an actionable next step.
- API returns structured `suggested_action` payload.
- UI offers direct navigation to execute suggested action.

### R5 - Security and secrets
- Azure credentials must stay backend-only.
- No Azure key/endpoint/deployment data in frontend bundle.
- Frontend communicates only with backend `/api/chat/*` endpoints.

### R6 - Resilience
- If Azure call fails, backend returns deterministic in-character fallback.
- Chat remains usable without hard failure.

## Technical Requirements

### T1 - Backend integration
- Add Azure OpenAI config in backend config and runtime env.
- Add NPC service with:
  - persona prompts,
  - opener selection,
  - nudge planner,
  - fallback logic.
- Add routes:
  - `POST /api/chat/start`
  - `POST /api/chat/message`
  - `GET /api/chat/session`
  - `POST /api/chat/reset`

### T2 - Frontend integration
- Extend types for chat payload.
- Extend API client with chat methods.
- Extend character store for transcript and suggested action.
- Render persistent dashboard-side CharacterPanel chat UI.

### T3 - UX quality constraints
- Chat panel must be readable on light parchment theme.
- Message bubbles must wrap and avoid overflow.
- Input supports Enter-to-send and Shift+Enter newline.

## Test Requirements

### API tests
- Auth required for chat endpoints.
- Start endpoint returns opener and suggested action.
- Message endpoint returns NPC reply and updated transcript.
- Session endpoint returns current transcript.
- Reset endpoint clears transcript.

### Frontend unit tests
- Store persists transcript and suggested action.
- API methods call correct endpoint contracts.

### E2E tests (Playwright)
- Login -> open dashboard -> chat panel visible.
- Send message -> response appears -> suggested action shown.
- Switch character -> panel remains functional.

## Acceptance Criteria
1. User can chat with Frodo/Sam/Gandalf from Dashboard.
2. NPC starts first with a random in-character opener.
3. NPC conversation remains multi-turn and coherent in session.
4. Each NPC response includes nudge-to-action behavior.
5. Feature works with fallback even when Azure config is missing.
6. API, unit, and E2E test files exist and pass in configured environments.
7. Implementation is not considered complete unless the docker-compose real-stack regression suite passes end-to-end (login/cors, map journey, NPC journey, NPC API) and targeted frontend chat unit tests pass.

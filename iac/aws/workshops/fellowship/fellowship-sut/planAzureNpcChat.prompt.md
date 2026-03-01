## Plan: Azure AI LOTR NPC Chat System

You want a realistic, in-character LOTR conversation experience where the NPC initiates dialogue, keeps a natural back-and-forth, and gently drives the user toward meaningful actions. We will implement this with Azure AI on the backend only (no secrets in frontend), launch chat first as a Dashboard side panel, and keep memory per login session for MVP. This fits your preferred implementation order and keeps scope controlled while still feeling premium and immersive. The plan below also includes requirements documentation, Playwright coverage, and technical feature explanations.

**Steps**
1. Define product contract and acceptance criteria in [REQUIREMENTS.md](iac/aws/workshops/fellowship/fellowship-sut/REQUIREMENTS.md), including: realistic persona behavior for Frodo/Sam/Gandalf, random opener types (question, judgment, reflection), “nudge toward action” objective, session-memory scope, and failure fallback behavior.
2. Add Azure AI backend configuration in [sut/backend/config.py](iac/aws/workshops/fellowship/fellowship-sut/sut/backend/config.py), [sut/backend/requirements.txt](iac/aws/workshops/fellowship/fellowship-sut/sut/backend/requirements.txt), and compose env wiring in [docker-compose.yml](iac/aws/workshops/fellowship/fellowship-sut/docker-compose.yml) for endpoint, deployment name, api version, and key placeholders (you will paste secrets later).
3. Implement NPC chat service layer in [sut/backend/services/npc_chat_service.py](iac/aws/workshops/fellowship/fellowship-sut/sut/backend/services/npc_chat_service.py) with: system prompts per character, style guardrails, random opener generator, action-nudge planner based on quest context, token/timeout limits, and deterministic fallback replies when Azure is unavailable.
4. Implement chat API routes in [sut/backend/routes/npc_chat.py](iac/aws/workshops/fellowship/fellowship-sut/sut/backend/routes/npc_chat.py) and register in [sut/backend/app.py](iac/aws/workshops/fellowship/fellowship-sut/sut/backend/app.py): start conversation, send user turn, fetch current session transcript, and reset session conversation.
5. Add session-scoped conversation state in backend using Flask session + lightweight in-memory/cache table strategy for MVP; keep explicit upgrade path documented for persistent storage in [ARCHITECTURE.md](iac/aws/workshops/fellowship/fellowship-sut/ARCHITECTURE.md).
6. Extend frontend API client in [sut/frontend/src/services/api.ts](iac/aws/workshops/fellowship/fellowship-sut/sut/frontend/src/services/api.ts) with typed chat endpoints and response contracts, keeping all Azure interactions strictly server-side.
7. Add NPC chat state and message models in [sut/frontend/src/types/index.ts](iac/aws/workshops/fellowship/fellowship-sut/sut/frontend/src/types/index.ts) and [sut/frontend/src/store/characterStore.ts](iac/aws/workshops/fellowship/fellowship-sut/sut/frontend/src/store/characterStore.ts): selected character, transcript, pending state, and current suggested action.
8. Build realistic chat UI in [sut/frontend/src/components/characters/CharacterPanel.tsx](iac/aws/workshops/fellowship/fellowship-sut/sut/frontend/src/components/characters/CharacterPanel.tsx) and mount it on Dashboard first via [sut/frontend/src/components/Dashboard.tsx](iac/aws/workshops/fellowship/fellowship-sut/sut/frontend/src/components/Dashboard.tsx): opener appears automatically, user can continue freely, and NPC shows contextual “next best action” chips.
9. Implement nudge-to-action UX loop in Dashboard: suggested action links directly to quests/filter states and map targets so the NPC persuasion translates into concrete app activity.
10. Add fallback and trust behaviors: if AI fails, keep in-character canned reply and preserve continuity; if response goes out-of-character, apply server post-filter and retry once.
11. Create backend API tests in [tests/test_npc_chat_api.py](iac/aws/workshops/fellowship/fellowship-sut/tests/test_npc_chat_api.py) for auth, session memory, opener generation, nudge payload, and fallback paths.
12. Create frontend unit tests in [sut/frontend/test/services/api.chat.test.ts](iac/aws/workshops/fellowship/fellowship-sut/sut/frontend/test/services/api.chat.test.ts) and [sut/frontend/test/store/characterStore.test.ts](iac/aws/workshops/fellowship/fellowship-sut/sut/frontend/test/store/characterStore.test.ts) for state transitions and contract handling.
13. Add Playwright E2E scenarios in [tests/test_npc_chat.py](iac/aws/workshops/fellowship/fellowship-sut/tests/test_npc_chat.py) and page object updates under [playwright/page_objects](playwright/page_objects): login → NPC auto-opener → multi-turn conversation → actionable nudge → user completes prompted action.
14. Update technical explanations and handoff docs in [ARCHITECTURE.md](iac/aws/workshops/fellowship/fellowship-sut/ARCHITECTURE.md), [SPECIFICATION.md](iac/aws/workshops/fellowship/fellowship-sut/SPECIFICATION.md), [HANDOFF.md](iac/aws/workshops/fellowship/fellowship-sut/HANDOFF.md), and [README.md](iac/aws/workshops/fellowship/fellowship-sut/README.md) with sequence diagrams, prompt strategy, safety model, env setup, and test execution.

**Verification**
- Backend: run pytest for new API tests and existing auth/quest suites.
- Frontend: run unit tests for api/store changes and production build.
- E2E: run Playwright journey validating opener realism, multi-turn continuity, and action conversion.
- Manual quality bar: each character sounds distinct and consistently “LOTR-authentic,” starts with varied opener tone, and nudges toward meaningful quest progress.

**Decisions**
- Chat launch surface: Dashboard side panel first.
- Memory model (MVP): per-login session only.
- Security model: Azure keys remain backend-only; frontend never receives secrets.
- Delivery order: keep your approved sequence; integrate this as Phase 7 core and Phase 8 polish/tests/docs completion path.

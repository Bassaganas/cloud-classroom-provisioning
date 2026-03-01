# Fellowship Frontend - Architecture & Data Flow

## System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USER BROWSER                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                        React Application                              │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                         │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  App Root (App.tsx)                                            │  │  │
│  │  │  • Initializes useQuestStore (global state)                   │  │  │
│  │  │  • Initializes useCharacterStore (NPC state)                  │  │  │
│  │  │  • Manages authentication flow                                │  │  │
│  │  │  • Routes to LoginPage / DashboardPage / QuestsPage / MapPage│  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                 ▼                                      │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Page Layer (Container Components)                            │  │  │
│  │  ├─────────────────────────────────────────────────────────────────┤  │  │
│  │  │                                                                 │  │  │
│  │  │  LoginPage        DashboardPage        QuestsPage    MapPage  │  │  │
│  │  │  ├─Fetch Auth     ├─Subscribe to      ├─Get filters  ├─Render│  │  │
│  │  │  ├─Validate Form  │ useQuestStats()   ├─Map quests   │ Map   │  │  │
│  │  │  └─Redirect       ├─Call Character    ├─Show Form    │ Markers│  │  │
│  │  │                   │ Service           └─Handle CRUD  └─Events│  │  │
│  │  │                   └─Render Stats                               │  │  │
│  │  │                                                                 │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                 ▼                                      │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Component Layer (Presentational)                             │  │  │
│  │  ├─────────────────────────────────────────────────────────────────┤  │  │
│  │  │                                                                 │  │  │
│  │  │  UI Components (src/components/ui/)                            │  │  │
│  │  │  ├─Button (epic, secondary, danger, small)                    │  │  │
│  │  │  ├─Card (parchment, dark)                                     │  │  │
│  │  │  ├─Badge (status, priority)                                   │  │  │
│  │  │  ├─Modal (forms, dialogs)                                     │  │  │
│  │  │  ├─Alert (info, warning, error)                               │  │  │
│  │  │  ├─Input/Textarea/Select (forms)                              │  │  │
│  │  │  └─Avatar (members, characters)                               │  │  │
│  │  │                                                                 │  │  │
│  │  │  Character Components (src/components/characters/)             │  │  │
│  │  │  └─CharacterPanel (Frodo/Sam/Gandalf dialogue)               │  │  │
│  │  │                                                                 │  │  │
│  │  │  Domain Components                                             │  │  │
│  │  │  ├─Dashboard, QuestList, QuestForm, MiddleEarthMap           │  │  │
│  │  │  └─Login, etc                                                  │  │  │
│  │  │                                                                 │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                 ▼                                      │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  State Management (Zustand Stores)                            │  │  │
│  │  ├─────────────────────────────────────────────────────────────────┤  │  │
│  │  │                                                                 │  │  │
│  │  │  questStore (src/store/questStore.ts)                          │  │  │
│  │  │  ├─ State: quests[], members[], locations[], user             │  │  │
│  │  │  ├─ Filters: status, type, priority, locationFilter, search   │  │  │
│  │  │  ├─ Mutations: setQuests, addQuest, updateQuest              │  │  │
│  │  │  ├─ Selectors: getFilteredQuests(), getQuestStats()          │  │  │
│  │  │  └─ Async: fetchAllData(), fetchQuests(), completeQuest()    │  │  │
│  │  │                                                                 │  │  │
│  │  │  characterStore (src/store/characterStore.ts)                 │  │  │
│  │  │  ├─ State: activeCharacter, currentDialogue, mood             │  │  │
│  │  │  ├─ Mutations: setCurrentDialogue, setCharacterMood           │  │  │
│  │  │  └─ Selectors: getCharacterAvatar(), getCharacterColor()      │  │  │
│  │  │                                                                 │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                 ▼                                      │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Services Layer (Business Logic)                              │  │  │
│  │  ├─────────────────────────────────────────────────────────────────┤  │  │
│  │  │                                                                 │  │  │
│  │  │  characterService (src/services/characterService.ts)           │  │  │
│  │  │  ├─ getWelcomeMessage(user, isNewLogin)                       │  │  │
│  │  │  ├─ getQuestAdvice(questType)                                 │  │  │
│  │  │  ├─ getDarkMagicWarning()                                     │  │  │
│  │  │  ├─ getCelebration(questsCompleted)                           │  │  │
│  │  │  ├─ getProgressRemark(completed, total, members)             │  │  │
│  │  │  ├─ getLoreQuote()                                            │  │  │
│  │  │  └─ getMood(darkMagicCount, completionRate)                  │  │  │
│  │  │                                                                 │  │  │
│  │  │  apiService (src/services/api.ts) ← Existing                  │  │  │
│  │  │  ├─ login(), logout(), getCurrentUser()                       │  │  │
│  │  │  ├─ getQuests(), createQuest(), updateQuest()                │  │  │
│  │  │  ├─ getMembers(), getLocations()                              │  │  │
│  │  │  └─ completeQuest()                                           │  │  │
│  │  │                                                                 │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                 ▼                                      │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Design System & Styling                                      │  │  │
│  │  ├─────────────────────────────────────────────────────────────────┤  │  │
│  │  │                                                                 │  │  │
│  │  │  designTokens (src/config/designTokens.ts)                     │  │  │
│  │  │  ├─ Colors: parchment, forest, gold, status, priority         │  │  │
│  │  │  ├─ Typography: Cinzel (epic), Lora (readable)                │  │  │
│  │  │  ├─ Spacing: xs(4px) → xxxl(64px)                             │  │  │
│  │  │  ├─ Shadows: sm, md, lg, epic, gold                           │  │  │
│  │  │  └─ Animations: fast(150ms), base(300ms), slow/epic           │  │  │
│  │  │                                                                 │  │  │
│  │  │  Tailwind CSS Configuration                                    │  │  │
│  │  │  ├─ tailwindcss v3 (utility-first CSS)                        │  │  │
│  │  │  ├─ postcss.config.js (CSS processing)                        │  │  │
│  │  │  ├─ tailwind.config.js (custom theme)                         │  │  │
│  │  │  └─ src/index.css (Tailwind directives + components)          │  │  │
│  │  │                                                                 │  │  │
│  │  │  Framer Motion                                                 │  │  │
│  │  │  └─ Component animations, transitions, micro-interactions     │  │  │
│  │  │                                                                 │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                         │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
                                       ▼
            ┌─────────────────────────────────────────────────────┐
            │           BACKEND API (Flask :5000)                 │
            ├─────────────────────────────────────────────────────┤
            │  /api/auth/login, /api/auth/logout                 │
            │  /api/quests, /api/quests/{id}                     │
            │  /api/members, /api/locations                      │
            │  /api/health                                        │
            └─────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

### 1. User Login Flow

```
User enters credentials
       ▼
LoginPage.tsx
└─ useQuestStore.setCurrentUser(user)
   └─ apiService.login(credentials)
      ├─ Backend validates
      ├─ Returns User + sessionCookie
      └─ questStore → currentUser
         └─ App.tsx redirects to /dashboard
            └─ questStore.fetchAllData()
               ├─ getQuests()
               ├─ getMembers()
               └─ getLocations()
```

### 2. Quest Display Flow

```
DashboardPage mounts
       ▼
useQuestStats() hook
       ▼
questStore.getQuestStats()
       │
       ├─ Selector counts: total, notBegun, inProgress, completed, blocked
       │
       └─ Return { total: 42, completed: 15, ... }
             ▼
         Component re-renders
             ▼
         Dashboard UI displays stats
```

### 3. Quest Creation/Update Flow

```
User clicks "Create Quest" button
       ▼
QuestForm Modal opens
       ▼
User fills form + clicks Submit
       ▼
Form validation (React Hook Form)
       ▼
questStore.createQuest({...questData})
       │
       ├─ apiService.createQuest() → Backend
       │  └─ Returns newQuest with id
       │
       └─ questStore.addQuest(newQuest)
          ├─ questStore.quests updated
          ├─ All subscribed components re-render
          │  ├─ QuestList shows new quest
          │  ├─ Dashboard stats update
          │  └─ Map adds new marker
          │
          └─ CharacterService.getCelebration()
             └─ CharacterPanel shows success message
```

### 4. Character Interaction Flow

```
User completes a quest
       ▼
Quest complete button clicked
       ▼
questStore.completeQuest(questId)
       │
       ├─ apiService.completeQuest() → Backend
       │  └─ Returns updated Quest (status = 'it_is_done')
       │
       └─ questStore.updateQuest(questId, updated)
          ├─ questStore.quests updated
          │
          └─ Page component (useEffect + questStats)
             └─ Detects completionRate changed
                └─ useCharacterStore.setCurrentDialogue(
                     CharacterService.getCelebration(count)
                   )
                   └─ CharacterPanel renders dialogue
                      └─ "Well done! X quests completed!"
```

### 5. Filter Flow

```
User changes status filter
       ▼
Filter chip clicked
       ▼
questStore.setStatusFilter('it_is_done')
       │
       └─ questStore.statusFilter updated
          └─ All useFilteredQuests() subscriptions update
             └─ QuestList re-renders with filtered values
```

---

## State Update Lifecycle

```
┌─────────────────────────────────────────────────┐
│  Event Triggered                                │
│  (User click, API response, etc)                │
└─────────────────────────────────────────────────┘
         ▼
┌─────────────────────────────────────────────────┐
│  Action called on Store                         │
│  questStore.getState().updateQuest(...)         │
│  OR                                             │
│  characterStore.getState().setCurrentDialogue(.)│
└─────────────────────────────────────────────────┘
         ▼
┌─────────────────────────────────────────────────┐
│  Store State Updated                            │
│  Zustand triggers optimization                  │
│  → Only subscribers get notified                │
└─────────────────────────────────────────────────┘
         ▼
┌─────────────────────────────────────────────────┐
│  Components Subscribe to Changed State          │
│  eg: DashboardPage calls useQuestStats()        │
│  React sees hook dependency changed             │
└─────────────────────────────────────────────────┘
         ▼
┌─────────────────────────────────────────────────┐
│  React Re-renders Component                    │
│  Only affected components update (fine-grained) │
│  NOT the entire React tree                      │
└─────────────────────────────────────────────────┘
         ▼
┌─────────────────────────────────────────────────┐
│  UI Updates in Browser                          │
│  Tailwind + Framer Motion handle animations     │
│  User sees updated interface                    │
└─────────────────────────────────────────────────┘
```

---

## Component Communication Patterns

### Pattern 1: Parent → Child (Props)
```typescript
// Parent
<QuestCard quest={quest} onComplete={handleComplete} />

// Child
export const QuestCard = ({ quest, onComplete }) => {
  return <Button onClick={() => onComplete(quest.id)}>Complete</Button>;
};
```

### Pattern 2: Child → Global State (Zustand)
```typescript
// Child updates store directly
const handleDelete = async (questId) => {
  await useQuestStore.getState().deleteQuest(questId);
};

// All other components subscribed to questStore automatically update
```

### Pattern 3: Sibling Communication (Store)
```typescript
// Component A (QuestList) reads state
const quests = useQuestStore((state) => state.getFilteredQuests());

// Component B (FilterPanel) updates state
const setFilter = useQuestStore((state) => state.setStatusFilter);

// Both update instantly when one changes
```

### Pattern 4: NPC Interactions (Character Store)
```typescript
// Any component can trigger character dialogue
useCharacterStore.getState().setCurrentDialogue({
  character: 'frodo',
  message: CharacterService.getEncouragement().message,
});

// CharacterPanel always shows whatever's in the store
```

---

## SOLID Principles in Practice

### Single Responsibility
- `questStore.ts` → Quest state only
- `characterStore.ts` → NPC state only
- `characterService.ts` → Character dialogue only
- `Button.tsx` → Button rendering only

### Open/Closed
- Add new dialogue types → Just add method to CharacterService
- Add new button variant → Just add to variantClasses object
- Add new selector → Just add to questStore

### Liskov Substitution
- Store selectors can be mocked in tests
- UI components accept props interface contracts

### Interface Segregation
- Export only needed hooks (`useQuests`, `useFilteredQuests`, etc)
- Don't export entire store to component
- Component doesn't see mutations it doesn't use

### Dependency Injection
- Stores passed via Zustand hooks (implicit DI)
- Services are singletons (no global polluters)
- Services can be mocked in tests

---

## Performance Optimizations

### Zustand Selectors (Automatic)
```typescript
// ✅ GOOD - Only component subscribes to this specific value
const quests = useQuestStore((state) => state.quests);

// Only re-renders when quests[] changes, not other store fields
```

### Derived Selectors
```typescript
// ✅ GOOD - Computed value cached
const getCompletionRate = useQuestStore((state) => state.getCompletionRate);

// Selector memoizes, prevents unnecessary recalculation
```

### Component Memoization
```typescript
// Can add memo() if list is very large
const QuestCard = React.memo(({ quest, onComplete }) => {
  // Only re-renders if quest prop changes
  return ...
});
```

---

## Testing Strategy

### Unit Tests
```
characterService.test.ts  ← Service logic tested in isolation
questStore.test.ts        ← Store mutations & selectors tested
Button.test.tsx           ← Component rendering tested
```

### Integration Tests
```
QuestsPage.test.tsx  ← Page + store + service together
LoginFlow.test.ts    ← End-to-end auth flow
```

### E2E Tests (Playwright)
```
tests/test_login.py        ← User perspective via browser
tests/test_dashboard.py    ← Full dashboard interaction
tests/test_map_page.py     ← Map functionality
```

---

## Scaling Patterns (If App Grows)

### More Complex State
```typescript
// Instead of simple filters, use immer middleware
import { immer } from 'zustand/middleware/immer';

const useQuestStore = create<State>()(
  immer((set) => ({ /* mutations are immutable by default */ }))
);
```

### Async Persistence
```typescript
// Persist store to localStorage
import { persist } from 'zustand/middleware';

const useQuestStore = create<State>()(
  persist((set) => ({ }), { name: 'quests-storage' })
);
```

### DevTools
```typescript
// Debug store in browser DevTools
import { devtools } from 'zustand/middleware';

const useQuestStore = create(devtools((set) => ({ })));
```

---

## Error Handling Flow

```
API Call Fails
    ▼
Catch in store async action
    ▼
questStore.setError(message)
    ▼
Component subscribed to error
    ▼
useQuestStore((state) => state.error)
    ▼
Render <Alert variant="error"> with message
    ▼
Auto-dismiss or manual close
```

---

**This architecture ensures scalability, testability, and maintainability while keeping code simple and LOTR-themed! 🧝‍♂️⚔️**

---

## Azure NPC Chat Architecture (Phase 7)

### System Boundary: Frontend ↔ Backend ↔ Azure AI

```
┌─────────────────────────────────┐
│     React Frontend              │
│   • No Azure secrets            │
│   • Calls /api/chat/* only      │
│   • Displays CharacterPanel     │
└──────────────┬──────────────────┘
               │ HTTP POST/GET
               ▼ (session-scoped)
┌─────────────────────────────────┐
│  Flask Backend                  │
│  ├─ routes/npc_chat.py          │
│  │  └─ Auth + route handling    │
│  ├─ services/npc_chat_service.py│
│  │  ├─ Persona prompts          │
│  │  ├─ Suggested action engine  │
│  │  ├─ OOC detection + fallback │
│  │  └─ Session store (in-memory)│
│  └─ config.py                   │
│     └─ Azure credentials (env)  │
└──────────────┬──────────────────┘
               │ HTTPS (outbound)
               │ Azure credentials
               ▼ (server-side only)
┌─────────────────────────────────┐
│  Azure OpenAI API               │
│  • gpt-4 deployment             │
│  • Chat completions endpoint    │
│  • Max tokens: 220 (tuned)      │
│  • Temperature: 0.85 (creative) │
└─────────────────────────────────┘
```

### Conversation Lifecycle

```
User Opens Dashboard (already authenticated)
       ▼
CharacterPanel renders with default character (Gandalf)
       ▼
componentDidMount → POST /api/chat/start
       │
       ├─ Backend validates session
       ├─ Calls NpcChatService.start_conversation()
       │  ├─ Picks random opener style (question, judgment, reflection)
       │  ├─ Computes suggested_action from quest state
       │  ├─ Stores conversation in session-scoped store
       │  └─ Returns { opener, suggested_action, character }
       │
       └─ Frontend displays opener + suggested_action CTA

User types message and sends
       ▼
POST /api/chat/message { character, message }
       │
       ├─ Backend validates auth + message length
       ├─ Calls NpcChatService.send_message()
       │  ├─ Retrieves conversation history (last 8 turns)
       │  ├─ Builds system prompt with persona + nudge context
       │  ├─ Calls Azure OpenAI with full context
       │  ├─ If out-of-character: retry with strict_mode=true
       │  ├─ If still OOC or failure: use fallback_reply()
       │  ├─ Appends user + npc turns to transcript (keep last 20)
       │  └─ Computes updated suggested_action
       │
       └─ Frontend appends messages to transcript
            + hydrates suggested_action CTA

User clicks suggested action CTA
       ▼
Frontend navigates to target route with query params
       │
       ├─ Map view: zooms to location + shows quest
       ├─ Quests view: prefills form with seed data
       └─ Returns to dashboard when action complete

User switches character or resets
       ▼
POST /api/chat/reset { character }
       ├─ Clears conversation from session store
       └─ Allows fresh opener for new character
```

### Prompt Strategy & NPC Personas

**Frodo Baggins (The Burden-Bearer)**
```
System Prompt:
  "You are Frodo Baggins speaking naturally and realistically in a modern chat.
   Stay warm, humble, burden-aware, brave under pressure, and concise.
   Do not mention being an AI. Keep tone immersive in Middle-earth context."

Opener Pool (random selection):
  • "Before we move, tell me this: what burden are you avoiding today?"
  • "I have a feeling the smallest task might matter most today. Which one is it?"
  • "If we could finish one thing before dusk, what should it be?"

Tone: Introspective, empathetic toward struggle, focuses on small wins
Nudge Style: "Even a small act done now can spare us greater trouble later."
```

**Samwise Gamgee (The Companion)**
```
System Prompt:
  "You are Samwise Gamgee speaking practically, loyal, earthy, and encouraging.
   Use plain words, gentle humor, and supportive tone.
   Do not mention being an AI. Keep the conversation immersive."

Opener Pool (random selection):
  • "Right then, what can we get done first so the road gets easier?"
  • "You look ready. Which quest should we push over the line now?"
  • "If we tidy one trouble before second breakfast, which one would you pick?"

Tone: Practical, optimistic, action-oriented, supportive
Nudge Style: "Start small, finish strong, then we move to the next."
```

**Gandalf (The Guide)**
```
System Prompt:
  "You are Gandalf speaking wise, direct, and strategic.
   You challenge, guide, and inspire action without sounding theatrical.
   Do not mention being an AI. Keep messages clear and purposeful."

Opener Pool (random selection):
  • "What is the one decision that would most improve the state of your quests right now?"
  • "Name the most urgent unfinished matter, and we shall act on it."
  • "Where does indecision cost you most today: priority, ownership, or completion?"

Tone: Authoritative, strategic, challenges assumptions
Nudge Style: "Do not wait for perfect conditions. Act on the essential next step."
```

**Conversation Rules (System Prompt Suffix)**
```
1. Keep replies to 1-4 short paragraphs
2. Ask one focused follow-up question often
3. Stay in character; do not use movie quotes verbatim
4. Gently guide the user toward practical action inside the quest tracker
5. Prioritize the suggested_action when drafting the NPC response
```

### Safety Model: Out-of-Character Detection & Fallback

**Out-of-Character Detection Filter**
```python
OOC Triggers: ["as an ai", "language model", "i cannot", "i can't", 
               "openai", "assistant", "i do not have access", "policy"]

Flow:
1. Azure returns completion
2. Convert to lowercase and check for OOC phrases
3. If OOC detected → Retry with strict_mode=true flag
   - Appends STRICT instruction to system prompt:
     "You MUST respond only in character. Do not mention being an AI, 
      language model, or any system limitations."
4. If still OOC or Azure times out → Use deterministic fallback
```

**Fallback Reply Strategy**
```
Base Fallback (randomly selected):
  • Frodo: "I hear you. Let us take one step that lightens the load now."
  • Sam: "Aye, that makes sense. Let us pick one task and finish it proper."
  • Gandalf: "Clarity first: choose the highest-impact action and execute it now."

Appended Question (context-aware):
  • If user sent message: "Will you take this next step now: {suggested_action.title}?"
  • If silent (just opened): "Which task will you commit to first?"

Result: User always gets in-character nudge; chat never blocks on Azure failure
```

### Session-Scoped Conversation State

**Storage Strategy (MVP: In-Memory)**
```
# Backend stores in-memory dict during user session
_conversation_store = {
  "{user_id}:{scope_id}:{character}": [
    { "role": "assistant", "content": "opener..." },
    { "role": "user", "content": "my message" },
    { "role": "assistant", "content": "npc reply" },
    ...
  ]
}

Scope ID: Generated once per login in session cookie, persists until logout
Transcript Limit: Keep last 20 turns (≈8 turns sent to Azure for context)
Lifetime: Session-scoped (cleared on logout)
```

**Upgrade Path (Future: Persistent Storage)**
```
When scaling beyond single-session MVP:
1. Add SQLAlchemy ConversationTurn model with FK to User
2. Store full history in DB instead of session memory
3. Migrate _conversation_store logic to model methods
4. Add ConversationTurn.query.filter_by(user_id, character).order_by(created_at)
5. Maintain same API contract; no frontend changes needed
```

### Goal Nudging Strategy (Suggested Action Engine)

**Priority Rules (evaluated in order)**

```
1. Resolve Dark Magic (Highest priority)
   └─ IF any quest.is_dark_magic == true AND status != "it_is_done"
      └─ THEN target = { route: "/map", query: { selectedQuestId, zoomToLocation } }

2. Finish Critical In-Progress
   └─ IF any quest.status == "the_road_goes_ever_on" AND priority == "Critical"
      └─ THEN target = { route: "/quests", query: { status, focusQuestId } }

3. Assign Unowned Critical
   └─ IF any quest.priority == "Critical" AND assigned_to == null
      └─ THEN target = { route: "/quests", query: { focusQuestId } }

4. Scout Hotspot (Map Exploration)
   └─ IF any quest.status == "not_yet_begun" AND location_id IS SET
      └─ THEN target = { route: "/map", query: { selectedQuestId, zoomToLocation } }

5. Advance Next Quest
   └─ IF any quest.status != "it_is_done"
      └─ THEN target = { route: "/quests", query: { focusQuestId } }

6. Propose Side Quest (Fallback for completion)
   └─ IF all quests.status == "it_is_done"
      └─ THEN target = { route: "/quests", query: { propose, seedTitle, seedDescription } }
```

**Response Format**
```json
{
  "goal_type": "resolve_dark_magic | finish_critical_in_progress | assign_critical | scout_map_hotspot | advance_next_quest | propose_side_quest",
  "title": "Short imperative nudge (e.g., 'Contain a dark magic quest')",
  "reason": "Rationale for why this action matters now",
  "target": {
    "route": "/map | /quests",
    "query": { "selectedQuestId": 5, "zoomToLocation": 3, ... }
  }
}
```

### Azure Credentials & Environment Setup

**Required Environment Variables** (set in docker-compose or CI/CD)
```bash
AZURE_OPENAI_ENDPOINT       # https://{resource}.openai.azure.com/
AZURE_OPENAI_API_KEY        # API key from Azure Portal
AZURE_OPENAI_DEPLOYMENT     # Deployment name (e.g., gpt-4-1-mini)
AZURE_OPENAI_API_VERSION    # 2024-02-15-preview or newer
AZURE_OPENAI_MAX_TOKENS     # 220 (default; tune for performance)
AZURE_OPENAI_TEMPERATURE    # 0.85 (default; ≥0.85 for personality)
```

**docker-compose.yml Wiring**
```yaml
services:
  backend:
    environment:
      - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT:-https://classroom-open-ai.openai.azure.com/}
      - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY:-}  # User supplies or .env file
      - AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT:-gpt-4-1-mini}
      - AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION:-2025-04-14}
```

**Local Testing with Azure**
```bash
# Set credentials in shell before docker-compose up
export AZURE_OPENAI_ENDPOINT=https://classroom-open-ai.openai.azure.com/
export AZURE_OPENAI_API_KEY=your-actual-api-key-here
export AZURE_OPENAI_DEPLOYMENT=gpt-4-1-mini

# Start compose (credentials auto-passed to backend container)
docker-compose up -d

# Chat endpoints now use Azure; fallback still works if key is invalid
curl -X POST http://localhost/api/chat/start \
  -H "Content-Type: application/json" \
  -d '{"character":"gandalf"}'
```

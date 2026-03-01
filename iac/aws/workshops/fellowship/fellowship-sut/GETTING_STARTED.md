# Getting Started - Fellowship Frontend Redesign

## Quick Start

### 1. Install Dependencies
```bash
cd iac/aws/workshops/fellowship/fellowship-sut/sut/frontend
npm install
```

### 2. Verify Everything Works
```bash
# Run TypeScript check
npx tsc --noEmit

# Run tests (should be 75+ tests)
npm run test

# Start development server
npm start
```

### 3. Open Browser
Navigate to `http://localhost:3000`

---

## Architecture at a Glance

### State Management (Zustand)
The app uses **Zustand stores** instead of React hooks for state:

```typescript
// ✅ CORRECT - Use custom hooks from store
import { useQuests, useQuestStats, useFilteredQuests } from '@/store/questStore';

function MyComponent() {
  const quests = useQuests();
  const stats = useQuestStats();
  const completionRate = useCompletionRate();
}
```

```typescript
// ❌ WRONG - Don't use useState for quest data
const [quests, setQuests] = useState([]); // This bypasses global state!
```

### Key Stores

**Quest Store** - `src/store/questStore.ts`
```typescript
// Get data
const quests = useQuestStore((state) => state.quests);
const filtered = useQuestStore((state) => state.getFilteredQuests());
const stats = useQuestStore((state) => state.getQuestStats());

// Update data
useQuestStore.getState().updateQuest(questId, { status: 'it_is_done' });
useQuestStore.getState().setStatusFilter('completed');

// Async operations
await useQuestStore.getState().fetchAllData();
await useQuestStore.getState().completeQuest(questId);
```

**Character Store** - `src/store/characterStore.ts`
```typescript
// Get current character dialogue
const { activeCharacter, currentDialogue, mood } = useCharacter();

// Show character message
useCharacterStore.getState().setCurrentDialogue({
  character: 'frodo',
  message: 'The road lies ahead...',
  mood: 'hopeful'
});
```

### Character Service (Business Logic)
Handles all NPC dialogue and character interactions:

```typescript
import { CharacterService } from '@/services/characterService';

// Get context-aware dialogue
const greeting = CharacterService.getWelcomeMessage(user, isNewLogin);
const advice = CharacterService.getQuestAdvice('The Journey');
const warning = CharacterService.getDarkMagicWarning();
const celebration = CharacterService.getCelebration(questsCompleted);
```

### UI Components
Reusable, styled components with Tailwind:

```typescript
import { Button, Card, Badge, StatusBadge, Modal, Alert, Input } from '@/components/ui';

// Example usage
<Card variant="parchment" hover>
  <h3>Quest Card</h3>
  <p>Description here</p>
  <StatusBadge status="it_is_done" />
  <Button variant="epic">Complete Quest</Button>
</Card>
```

---

## Component Anatomy

### Page (Container)
```typescript
// pages/QuestsPage.tsx
import { useQuestStore } from '@/store/questStore';
import { CharacterService } from '@/services/characterService';

export const QuestsPage = () => {
  const quests = useQuestStore((state) => state.getFilteredQuests());
  
  // Load data on mount
  useEffect(() => {
    useQuestStore.getState().fetchAllData();
  }, []);
  
  return (
    <div>
      <QuestList quests={quests} />
      <CharacterPanel />
    </div>
  );
};
```

### Component (Presentational)
```typescript
// components/QuestList.tsx
export const QuestList: React.FC<{ quests: Quest[] }> = ({ quests }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {quests.map((quest) => (
        <QuestCard key={quest.id} quest={quest} />
      ))}
    </div>
  );
};
```

---

## Design Tokens

All colors, spacing, and typography defined in one place:

```typescript
import { Colors, Typography, Spacing } from '@/config/designTokens';

// No magic numbers!
const padding = Spacing.lg;        // "1.5rem"
const color = Colors.status.ready; // "#10B981"
const font = Typography.fonts.epic; // "Cinzel, serif"
```

---

## Common Tasks

### Add a New Feature

1. **Define in Store** (state + mutations)
   ```typescript
   // questStore.ts
   isDarkMagicWarning: boolean,
   setDarkMagicWarning: (active: boolean) => void,
   ```

2. **Create Service Logic** (business rules)
   ```typescript
   // characterService.ts
   static getDarkMagicWarning(): DialogueResponse { ... }
   ```

3. **Create Component** (UI)
   ```typescript
   // components/DarkMagicAlert.tsx
   export const DarkMagicAlert = () => {
     const isDark = useDarkMagicState();
     if (!isDark) return null;
     return <Alert variant="warning">Sauron is watching...</Alert>;
   };
   ```

4. **Integrate in Page**
   ```typescript
   // pages/DashboardPage.tsx
   <DarkMagicAlert />
   ```

### Add Tests

```typescript
// test/components/DarkMagicAlert.test.tsx
describe('DarkMagicAlert', () => {
  it('should show alert when dark magic is active', () => {
    // 1. Setup
    useCharacterStore.setState({ isDarkMagicActive: true });
    
    // 2. Render
    const { getByText } = render(<DarkMagicAlert />);
    
    // 3. Assert
    expect(getByText(/Sauron/)).toBeInTheDocument();
  });
});
```

### Add a Character Dialogue

```typescript
// services/characterService.ts
const DIALOGUES = {
  customGreeting: [
    'Frodo: Welcome back, friend!',
    'Sam: Good to see you again!',
  ],
};

static getCustomGreeting(): DialogueResponse {
  const message = DIALOGUES.customGreeting[...];
  return { character: 'frodo', message, mood: 'hopeful' };
}
```

---

## Common Issues & Solutions

### Issue: Styles not applying
**Solution**: Make sure Tailwind config is loaded
- Check `npm run build` output includes Tailwind CSS
- Verify `postcss.config.js` exists
- Restart dev server: `npm start`

### Issue: Types don't match backend
**Solution**: Update `src/types/index.ts`
- Keep Quest/User/Member interfaces in sync with API
- Run `npx tsc --noEmit` to catch type errors

### Issue: Character not showing
**Solution**: Ensure CharacterPanel is rendered
```typescript
// Must be in root App.tsx or page
import { CharacterPanel } from '@/components/characters/CharacterPanel';

<div>
  <Routes>...</Routes>
  <CharacterPanel />  // Add this!
</div>
```

### Issue: Tests failing
**Solution**: Check store state isolation
```typescript
beforeEach(() => {
  // Reset store before each test
  useQuestStore.setState({
    quests: [],
    statusFilter: null,
  });
});
```

---

## Development Workflow

### Feature Branch
```bash
git checkout -b phase/3-dashboard-redesign
```

### Development
```bash
npm start              # Dev server
npm run test:watch    # Tests in watch mode
```

### Before Commit
```bash
npm run test          # All tests pass
npx tsc --noEmit      # No type errors
npm run build         # Production build works
```

### Commit
```bash
git add .
git commit -m "feat: Add dashboard progress bar with character guidance"
git push origin phase/3-dashboard-redesign
```

---

## File Structure

```
sut/frontend/
├── public/                    # Static assets
├── src/
│   ├── components/            # Reusable components
│   │   ├── ui/               # Design system (Button, Card, etc)
│   │   ├── characters/       # NPC components
│   │   ├── Dashboard.tsx     # Existing components
│   │   ├── Login.tsx
│   │   └── ...
│   ├── pages/                # Route containers
│   │   ├── DashboardPage.tsx
│   │   ├── QuestsPage.tsx
│   │   ├── MapPage.tsx
│   │   └── LoginPage.tsx
│   ├── services/             # Business logic
│   │   ├── api.ts           # HTTP (existing)
│   │   └── characterService.ts
│   ├── store/                # Zustand stores
│   │   ├── questStore.ts
│   │   └── characterStore.ts
│   ├── config/               # Design system
│   │   └── designTokens.ts
│   ├── types/                # TypeScript interfaces
│   │   └── index.ts
│   ├── utils/                # Helpers
│   ├── App.tsx               # Root component
│   ├── App.css               # App styles (Tailwind will replace)
│   ├── index.css             # Global styles + Tailwind
│   └── index.tsx             # Entry point
├── test/                      # Test files (mirrors src/)
│   ├── services/
│   ├── store/
│   └── components/
├── package.json              # Dependencies
├── tsconfig.json             # TypeScript config
├── tailwind.config.js        # Tailwind theme
├── postcss.config.js         # CSS processing
├── vitest.config.ts          # Test config
└── README.md
```

---

## Key Files to Know

**Store** (Global State)
- `src/store/questStore.ts` - Quests, members, locations, filters
- `src/store/characterStore.ts` - NPC state

**Services** (Business Logic)
- `src/services/characterService.ts` - NPC dialogue
- `src/services/api.ts` - HTTP calls (don't modify!)

**Components** (UI)
- `src/components/ui/` - All design system components
- `src/components/characters/CharacterPanel.tsx` - NPC UI
- `src/pages/` - Page containers

**Design**
- `src/config/designTokens.ts` - Colors, spacing, typography
- `tailwind.config.js` - Tailwind customization
- `src/index.css` - Global Tailwind directives

---

## Next Phases Overview

| Phase | Focus | Timeline |
|-------|-------|----------|
| **2** | Login page redesign | 2 days |
| **3** | Dashboard with progress | 3 days |
| **4** | Quests filtering & CRUD | 4 days |
| **5** | Map with Sauron | 3 days |

Each phase builds on previous, enabling incremental testing and feedback.

---

## Getting Help

### Check These First
1. **Type Errors**: Run `npx tsc --noEmit`
2. **Component Issues**: Check `src/components/ui/index.ts` exports
3. **Store Issues**: Verify `beforeEach` resets in tests
4. **Routing Issues**: Ensure all routes in `App.tsx` are protected with user check

### Review Previous Phase Implementations
- Reference Phase 1 for store patterns
- Reference Phase 6 for UI component patterns
- Reference CharacterService for dialogue patterns

### Run Tests to Validate
```bash
npm run test                    # All tests
npm run test -- --grep="Quest" # Filter tests
npm run test:coverage          # Coverage report
```

---

**Ready to build the future of fellowship! 🧝‍♂️**

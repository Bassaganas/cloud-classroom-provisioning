# Phase 2: Login Page Redesign - Implementation Plan

**Objective**: Create an immersive, game-like login experience with animated hero background, character greeting, and form validation.

**Timeline**: 2 days | **Story Points**: 8 | **Status**: Ready to Start ✅

---

## Requirements

### Visual Design
- [ ] Full-height hero background (animated LOTR landscape OR particle effect)
- [ ] Centered card container with parchment texture gradient
- [ ] Gandalf or character welcome message appears on load
- [ ] Form inputs with glow effects on focus
- [ ] Remember Me checkbox with visual toggle
- [ ] Show/hide password toggle with eye icon
- [ ] Loading state with animated Gandalf staff spinner
- [ ] Error state with animated shake + Alert component
- [ ] Success animation before redirect

### Functional Requirements
- [ ] Login form validation (username + password required)
- [ ] Submit via existing `apiService.login()`
- [ ] Character greeting varies (Frodo/Sam 50/50)
- [ ] Character speaks based on first login vs returning user
- [ ] Save authentication token to cookie (already done by backend)
- [ ] Redirect to dashboard on success
- [ ] Show friendly error messages on failure
- [ ] "Hint: try festival123" helper text visible

### Character Integration
- [ ] Get welcome dialogue from `CharacterService.getWelcomeMessage(user, isNewLogin)`
- [ ] Display character avatar (emoji) in corner
- [ ] Animated speech bubble with LOTR quote
- [ ] Character mood displayed (hopeful by default)

### Accessibility
- [ ] Form labels properly associated with inputs
- [ ] Error messages with aria-live
- [ ] Keyboard navigation working (Tab, Enter)
- [ ] Auto-focus on first input

---

## Component Structure

### Files to Update/Create

```
src/pages/
├── LoginPage.tsx (⭐ UPDATE)
│   ├─ Import components from ui + characterService
│   ├─ Manage form state (useForm hook + useState for character)
│   ├─ Call apiService.login()
│   ├─ Render hero background
│   ├─ Render form card
│   └─ Show character greeting
│
└── styles/
    └── LoginPage.css (or use Tailwind classes)

src/components/
├── Login.tsx (⭐ UPDATE - Keep existing, just add styling)
│   └─ Form implementation (fields, buttons, validation)
│
└── ui/ (⭐ USE EXISTING)
    ├─ Button.tsx (already created)
    ├─ Input.tsx (already created)
    ├─ Alert.tsx (already created)
    └─ Avatar.tsx (already created)

test/pages/
└── LoginPage.test.tsx (⭐ CREATE)
    ├─ Test form submission
    ├─ Test character greeting
    ├─ Test error handling
    └─ Test loading state
```

---

## Detailed Implementation Steps

### Step 1: Update Login Form (`src/components/Login.tsx`)

**Current State**: Basic form component exists  
**Action**: Add Tailwind classes and upgrade to new UI components

```tsx
import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button, Input, Alert } from '@/components/ui';
import { LoginRequest } from '@/types';

interface LoginProps {
  onLogin: (user: any) => void;
  isLoading?: boolean;
  error?: string;
}

export const Login: React.FC<LoginProps> = ({ onLogin, isLoading, error }) => {
  const { register, handleSubmit, formState: { errors } } = useForm<LoginRequest>();
  const [showPassword, setShowPassword] = useState(false);

  return (
    <form className="space-y-4" onSubmit={handleSubmit(...)} noValidate>
      {/* Username Input */}
      <Input
        label="Username"
        {...register('username', { required: 'Username required' })}
        error={errors.username?.message}
        placeholder="Your fellowship name"
        className="focus:glow-gold"
      />

      {/* Password Input with Toggle */}
      <div className="relative">
        <Input
          label="Password"
          type={showPassword ? 'text' : 'password'}
          {...register('password', { required: 'Password required' })}
          error={errors.password?.message}
          placeholder="Your secret password"
        />
        <button
          type="button"
          onClick={() => setShowPassword(!showPassword)}
          className="absolute right-3 top-9 text-parchment-light hover:text-gold-default"
        >
          {showPassword ? '👁️' : '🙈'}
        </button>
      </div>

      {/* Remember Me Checkbox */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          className="w-4 h-4 rounded border-gold-dark/50 accent-gold-default"
        />
        <span className="text-sm text-parchment-light">Remember me on this device</span>
      </label>

      {/* Error Alert */}
      {error && (
        <Alert variant="error" title="Authentication Failed" onClose={...}>
          {error}
        </Alert>
      )}

      {/* Hint Text */}
      <p className="text-xs text-text-secondary italic text-center">
        Demo credentials: username/password or try festival123
      </p>

      {/* Submit Button */}
      <Button
        variant="epic"
        type="submit"
        isLoading={isLoading}
        className="w-full"
      >
        {isLoading ? 'Entering Middle-earth...' : 'Enter the Fellowship'}
      </Button>
    </form>
  );
};
```

### Step 2: Implement LoginPage (`src/pages/LoginPage.tsx`)

**Action**: Create immersive page with hero background, character greeting, form card

```tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Login } from '@/components/Login';
import { Card, Avatar } from '@/components/ui';
import { CharacterService } from '@/services/characterService';
import { useCharacterStore } from '@/store/characterStore';
import { apiService } from '@/services/api';

interface LoginPageProps {
  onLogin: (user: any) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [greeting, setGreeting] = useState(null);
  
  const setCurrentDialogue = useCharacterStore((state) => state.setCurrentDialogue);

  // Initialize character greeting on mount
  useEffect(() => {
    const welcome = CharacterService.getWelcomeMessage({} as any, true);
    setGreeting(welcome);
    setCurrentDialogue(welcome);
  }, [setCurrentDialogue]);

  const handleLogin = async (credentials: any) => {
    setIsLoading(true);
    setError(null);

    try {
      const user = await apiService.login(credentials);
      
      // Show success celebration
      const celebration = CharacterService.getLoreQuote();
      setCurrentDialogue(celebration);

      // Call parent handler
      onLogin(user);

      // Redirect (will be handled by App.tsx based on auth state)
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed. Please try again.';
      setError(message);
      
      // Show error from character
      const warning = CharacterService.getDarkMagicWarning();
      setCurrentDialogue(warning);
      
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background-primary flex items-center justify-center p-4 overflow-hidden">
      {/* Animated Background with Parallax */}
      <motion.div
        className="absolute inset-0 opacity-20 bg-gradient-to-br from-forest-dark via-background-primary to-gold-dark"
        animate={{
          backgroundPosition: ['0% 0%', '100% 100%'],
        }}
        transition={{ duration: 20, repeat: Infinity, repeatType: 'reverse' }}
      />

      {/* Floating Particles Effect (Optional) */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(20)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-1 h-1 bg-gold-default rounded-full opacity-20"
            initial={{ x: Math.random() * 400, y: Math.random() * -400 }}
            animate={{ y: 400 }}
            transition={{
              duration: Math.random() * 10 + 20,
              repeat: Infinity,
            }}
            style={{ left: `${Math.random() * 100}%` }}
          />
        ))}
      </div>

      {/* Content Container */}
      <div className="relative z-10 w-full max-w-md">
        {/* Welcome Title */}
        <motion.h1
          className="text-center font-epic text-4xl text-parchment-light mb-2 glow-gold"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          The Fellowship's Quest
        </motion.h1>

        <motion.p
          className="text-center text-parchment-default mb-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          One does not simply enter without credentials...
        </motion.p>

        {/* Login Card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <Card variant="parchment" className="shadow-epic">
            <Login
              onLogin={handleLogin}
              isLoading={isLoading}
              error={error}
            />
          </Card>
        </motion.div>

        {/* Character Greeting Display */}
        {greeting && (
          <motion.div
            className="mt-6 p-4 bg-background-secondary rounded-lg border-2 border-gold-default"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            <div className="flex items-start gap-3">
              <Avatar
                emoji={greeting.character === 'frodo' ? '🧝' : '👨‍🌾'}
                size="lg"
              />
              <div>
                <h3 className="font-epic text-parchment-light capitalize">
                  {greeting.character}
                </h3>
                <p className="text-sm text-parchment-light italic mt-1">
                  "{greeting.message}"
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* Footer */}
        <motion.p
          className="text-center text-xs text-text-secondary mt-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.6 }}
        >
          Welcome to the Fellowship of the Build
        </motion.p>
      </div>
    </div>
  );
};

export default LoginPage;
```

### Step 3: Create Tests (`test/pages/LoginPage.test.tsx`)

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginPage } from '@/pages/LoginPage';
import { apiService } from '@/services/api';

vi.mock('@/services/api');

describe('LoginPage', () => {
  const mockOnLogin = vi.fn();

  beforeEach(() => {
    mockOnLogin.mockClear();
  });

  it('should render login form', () => {
    render(<LoginPage onLogin={mockOnLogin} />);

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /enter the fellowship/i })).toBeInTheDocument();
  });

  it('should show character greeting on mount', async () => {
    render(<LoginPage onLogin={mockOnLogin} />);

    await waitFor(() => {
      expect(screen.getByText(/frodo|sam/i)).toBeInTheDocument();
    });
  });

  it('should toggle password visibility', async () => {
    const user = userEvent.setup();
    render(<LoginPage onLogin={mockOnLogin} />);

    const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement;
    const toggleButton = screen.getByRole('button', { name: /👁️|🙈/i });

    expect(passwordInput.type).toBe('password');

    await user.click(toggleButton);
    expect(passwordInput.type).toBe('text');
  });

  it('should submit form with credentials', async () => {
    const user = userEvent.setup();
    const mockUser = { id: 1, username: 'frodo' };

    vi.mocked(apiService.login).mockResolvedValue(mockUser);

    render(<LoginPage onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText(/username/i), 'frodo');
    await user.type(screen.getByLabelText(/password/i), 'festival123');
    await user.click(screen.getByRole('button', { name: /enter the fellowship/i }));

    await waitFor(() => {
      expect(mockOnLogin).toHaveBeenCalledWith(mockUser);
    });
  });

  it('should show error on login failure', async () => {
    const user = userEvent.setup();

    vi.mocked(apiService.login).mockRejectedValue(
      new Error('Invalid credentials')
    );

    render(<LoginPage onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText(/username/i), 'frodo');
    await user.type(screen.getByLabelText(/password/i), 'wrong');
    await user.click(screen.getByRole('button', { name: /enter the fellowship/i }));

    await waitFor(() => {
      expect(screen.getByText(/Invalid credentials/)).toBeInTheDocument();
    });
  });

  it('should show loading state during submission', async () => {
    const user = userEvent.setup();

    vi.mocked(apiService.login).mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 1000))
    );

    render(<LoginPage onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText(/username/i), 'frodo');
    await user.type(screen.getByLabelText(/password/i), 'festival123');
    await user.click(screen.getByRole('button', { name: /enter the fellowship/i }));

    expect(screen.getByText(/Entering Middle-earth/)).toBeInTheDocument();
  });
});
```

### Step 4: Update App.tsx (Optional Enhancement)

The App.tsx is already updated, but you might want to enhance the loading screen styling:

```tsx
// In App.tsx loading render
{isLoading && (
  <div className="fixed inset-0 bg-background-primary/80 backdrop-blur-sm flex items-center justify-center z-50 animate-fadeIn">
    <div className="text-center">
      {/* Animated Gandalf Staff */}
      <motion.div
        className="text-6xl mb-4"
        animate={{ rotate: 360, y: [0, -10, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
      >
        🧙‍♂️
      </motion.div>
      <p className="text-parchment-light font-epic text-2xl">
        Loading your Fellowship...
      </p>
    </div>
  </div>
)}
```

---

## Styling Details

### Hero Background Options

**Option A: Gradient with Parallax** (Recommended - Lighter)
```CSS
background: linear-gradient(to bottom right, #2D5016, #0F1117, #8B5CF6);
animation: shift 20s ease-in-out infinite;

@keyframes shift {
  0%, 100% { background-position: 0% 0%; }
  50% { background-position: 100% 100%; }
}
```

**Option B: Particle Effect** (Heavier - Already in code above)
- 20 floating particles
- Randomized positions and timings
- Opacity 20% for subtlety

**Option C: Texture Overlay** (Elegant)
```CSS
background-image: 
  url('data:image/svg+xml,...'), 
  linear-gradient(...);
opacity: 0.05;
mix-blend-mode: multiply;
```

### Form Card Styling
- Parchment gradient (using Card component)
- Border with gold-dark/20 transparency
- Shadow epic class for glow
- Hover elevation
- Max-width: 28rem (448px)

### Character Greeting Box
- Dark background variant
- Gold border 2px
- Flex layout for avatar + content
- Italic quoted text

---

## Acceptance Criteria

- [ ] Visual: Hero background animated smoothly
- [ ] Visual: Form card centered with parchment styling
- [ ] Visual: Character avatar shows in greeting
- [ ] Visual: All interactions have smooth animations
- [ ] Functional: Form validates username + password required
- [ ] Functional: Login request sent to backend
- [ ] Functional: User redirected to dashboard on success
- [ ] Functional: Error message displayed on failure
- [ ] Character: Greeting varies between Frodo and Sam
- [ ] Character: Character mood displayed
- [ ] Character: Dialogue changes between first login and returning
- [ ] Accessibility: Form labels properly associated
- [ ] Accessibility: Keyboard navigation works (Tab, Enter)
- [ ] Accessibility: Error messages announced to screen readers
- [ ] Tests: All 6+ test cases passing
- [ ] Performance: No layout shifts, smooth animations

---

## Rollout Checklist

Before merging to main:

- [ ] All tests pass: `npm run test`
- [ ] No TypeScript errors: `npx tsc --noEmit`
- [ ] Visually reviewed in browser on desktop + mobile
- [ ] Form works with valid credentials
- [ ] Error messages display correctly
- [ ] Character greeting shows and updates
- [ ] Loading state works smoothly
- [ ] Console is error-free
- [ ] Tailwind classes compile without warnings
- [ ] Performance acceptable (Lighthouse > 80)

---

## Dependencies Already Available

✅ All needed imports already exist in codebase:
- `Button`, `Input`, `Card`, `Alert`, `Avatar` from `@/components/ui`
- `CharacterService` from `@/services/characterService`
- `useCharacterStore` from `@/store/characterStore`
- `Framer Motion` for animations
- `React Hook Form` for form validation
- `apiService.login()` for backend call

---

## Next Phase (Phase 3)

After Phase 2 (Login) is complete, the next phase will be the **Dashboard redesign**, which will use:
- `useQuestStats()` hook from questStore
- `CharacterService.getProgressRemark()` for dynamic commentary
- New Dashboard components showing progress bars, threat levels, and character guidance

---

**Ready to build the most epic login screen in Middle-earth! 🧝‍♂️✨**

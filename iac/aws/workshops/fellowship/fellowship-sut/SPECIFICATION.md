# The Fellowship's Quest List - Complete Specification

## Overview

"The Fellowship's Quest List" is a LOTR-themed todo list application that allows Fellowship members to track their epic journey through Middle-earth. The application combines simple todo list functionality with rich LOTR storytelling, creating an engaging and immersive experience while maintaining ease of use.

## Main Requirements

### Functional Requirements

1. **User Authentication**
   - Fellowship members can log in with their character credentials
   - Session-based authentication
   - Each member has a unique role (Ring-bearer, Companion, Ranger, etc.)

2. **Quest Management (Core Todo List Functionality)**
   - Create new quests (Propose a Quest)
   - View all quests (The Scrolls of Middle-earth)
   - Update quest details (Revise the Quest)
   - Mark quests as complete (The Quest Is Done)
   - Delete quests (Abandon Quest)
   - Filter quests by status, type, priority, and dark magic flag

3. **Quest Attributes**
   - Title and description
   - Status (LOTR terminology)
   - Quest type (The Journey, The Battle, The Fellowship, The Ring, Dark Magic)
   - Priority (Critical, Important, Standard)
   - Location (Middle-earth locations)
   - Assigned Fellowship member
   - Dark magic flag (for infrastructure bug testing)
   - Character quote (shown on completion)
   - Timestamps (created, updated, completed)

4. **Dashboard (The Council Chamber)**
   - Quest statistics overview
   - Journey progress visualization
   - Recent quests display
   - Dark magic quest warnings
   - Character-specific statistics

5. **Visual Design**
   - LOTR-themed color palette
   - Epic typography
   - Parchment-style backgrounds
   - Character avatars/icons
   - Priority indicators (colored rings)
   - Dark magic quest special styling

### Non-Functional Requirements

1. **Performance**
   - Page load time < 2 seconds
   - API response time < 500ms
   - Smooth UI interactions

2. **Usability**
   - Intuitive navigation
   - Clear visual hierarchy
   - Accessible design (WCAG 2.1 AA minimum)

3. **Maintainability**
   - Clean code structure
   - Comprehensive test coverage
   - Well-documented API

4. **Compatibility**
   - Works on modern browsers (Chrome, Firefox, Safari, Edge)
   - Responsive design for desktop and tablet
   - Mobile-friendly interface

## User Features

### 1. Authentication & User Management

**Login Page**
- Welcome message: "Welcome to the Fellowship Quest Tracker"
- Username and password fields
- Character selection hint (shows available Fellowship members)
- LOTR-themed styling with epic background

**User Roles**
- Frodo Baggins (Ring-bearer, Hobbit)
- Samwise Gamgee (Companion, Hobbit)
- Aragorn (Ranger, Human)
- Legolas (Archer, Elf)
- Gimli (Warrior, Dwarf)
- Gandalf (Guide, Wizard)

**Session Management**
- Persistent login session
- Logout functionality ("Leave the Fellowship")
- Session timeout handling

### 2. Quest List (The Scrolls of Middle-earth)

**Quest Display**
- Card-based layout with parchment styling
- Quest title (prominent, epic font)
- Quest description (readable body text)
- Status badge with LOTR terminology:
  - "Not Yet Begun" (pending) - Gray/neutral
  - "The Road Goes Ever On..." (in_progress) - Yellow/amber
  - "It Is Done" (completed) - Green/gold
  - "The Shadow Falls" (blocked) - Red/dark
- Quest type indicator with icon:
  - The Journey (compass icon)
  - The Battle (sword icon)
  - The Fellowship (group icon)
  - The Ring (ring icon)
  - Dark Magic (Eye of Sauron icon)
- Priority indicator (colored ring):
  - Critical (red ring)
  - Important (gold ring)
  - Standard (silver ring)
- Location badge (Middle-earth location name)
- Assigned member (character name with role)
- Character quote (displayed on completed quests)
- Dark magic styling (red glow, dark theme for dark magic quests)

**Quest Actions**
- Mark as complete button (with character quote display)
- Edit quest button
- Delete quest button (with confirmation)
- View quest details

**Filtering & Sorting**
- Filter by status
- Filter by quest type
- Filter by priority
- Filter by dark magic flag
- Filter by location
- Filter by assigned member
- Sort by priority, date, or status

### 3. Quest Creation/Editing (Propose/Revise a Quest)

**Quest Form Fields**
- Title (required, text input)
- Description (textarea with placeholder: "Describe the quest in epic detail...")
- Quest Type (dropdown):
  - The Journey
  - The Battle
  - The Fellowship
  - The Ring
  - Dark Magic
- Priority (dropdown):
  - Critical
  - Important
  - Standard
- Status (dropdown with LOTR terminology)
- Location (dropdown with Middle-earth locations)
- Assign To (dropdown with Fellowship members)
- Dark Magic checkbox (for creating test challenge quests)
- Character Quote (optional, text input for completion quote)

**Form Validation**
- Title required
- Quest type required
- Priority required
- Status required
- Location optional
- Assigned member optional

### 4. Dashboard (The Council Chamber)

**Welcome Section**
- Personalized greeting: "Welcome, [Character Name]!"
- Subtitle: "Track the Fellowship's journey through Middle-earth"

**Statistics Cards**
- Total Quests (all quests count)
- Not Yet Begun (pending count)
- The Road Goes Ever On (in_progress count)
- It Is Done (completed count)
- The Shadow Falls (blocked/dark magic count)
- Active Fellowship Members

**Journey Progress**
- Visual progress bar showing journey from Shire → Mordor
- Milestone markers:
  - The Shire (start)
  - Rivendell
  - Moria
  - Lothlórien
  - Rohan
  - Mordor (end)
- Progress calculated based on completed quests

**Recent Quests**
- Last 5 quests (most recent first)
- Quick view with status and location
- Click to view full details

**Dark Magic Warning**
- Alert banner if dark magic quests exist
- Count of dark magic quests
- Link to filter dark magic quests

**Character Statistics**
- Quests assigned to current user
- Quests completed by current user
- User's contribution to Fellowship progress

### 5. Quest Completion

**Completion Flow**
1. User clicks "Mark Complete" button
2. Quest status changes to "It Is Done"
3. Completion timestamp recorded
4. Character quote displayed (if available)
5. Celebration animation (subtle, epic)
6. Journey progress updates
7. Quest moves to completed section

**Character Quotes**
- Each quest can have an optional character quote
- Quote displayed prominently on completion
- Examples:
  - Frodo: "I will take the Ring, though I do not know the way."
  - Sam: "I can't carry it for you, but I can carry you!"
  - Gandalf: "All we have to decide is what to do with the time that is given us."

### 6. Dark Magic Quests

**Visual Identification**
- Red/dark color scheme
- Eye of Sauron icon
- Special border styling (red glow)
- Warning badge: "Dark Magic"

**Purpose**
- Represents infrastructure bugs for testing
- Teams must detect and fix these issues
- Special handling in tests

**Behavior**
- May appear/disappear randomly (simulated bug)
- Completion may fail silently (simulated bug)
- May corrupt other quests (simulated bug)
- Filterable for testing purposes

## API Endpoints

### Base URL
- Local: `http://localhost/api`
- Production: `http://<ec2-ip>/api`

### Authentication Endpoints

#### POST /api/auth/login
Login as a Fellowship member.

**Request:**
```json
{
  "username": "frodo_baggins",
  "password": "fellowship123"
}
```

**Response (200):**
```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "username": "frodo_baggins",
    "email": "frodo_baggins@fellowship.com",
    "role": "Frodo Baggins",
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

**Response (401):**
```json
{
  "error": "Invalid credentials"
}
```

#### POST /api/auth/logout
Logout current user.

**Response (200):**
```json
{
  "message": "Logout successful"
}
```

#### GET /api/auth/me
Get current authenticated user.

**Response (200):**
```json
{
  "id": 1,
  "username": "frodo_baggins",
  "email": "frodo_baggins@fellowship.com",
  "role": "Frodo Baggins",
  "created_at": "2024-01-15T10:00:00Z"
}
```

**Response (401):**
```json
{
  "error": "Not authenticated"
}
```

### Quest Endpoints

#### GET /api/quests
Get all quests with optional filtering.

**Query Parameters:**
- `status` (optional): Filter by status (`not_yet_begun`, `the_road_goes_ever_on`, `it_is_done`, `the_shadow_falls`)
- `quest_type` (optional): Filter by type (`The Journey`, `The Battle`, `The Fellowship`, `The Ring`, `Dark Magic`)
- `priority` (optional): Filter by priority (`Critical`, `Important`, `Standard`)
- `dark_magic` (optional): Filter dark magic quests (`true`/`false`)
- `location_id` (optional): Filter by location ID
- `assigned_to` (optional): Filter by assigned user ID

**Response (200):**
```json
[
  {
    "id": 1,
    "title": "Destroy the One Ring",
    "description": "Journey to the fires of Mount Doom and cast the Ring into the flames where it was forged. The fate of Middle-earth depends on this quest.",
    "status": "the_road_goes_ever_on",
    "quest_type": "The Ring",
    "priority": "Critical",
    "is_dark_magic": false,
    "location_id": 6,
    "location_name": "Mordor",
    "assigned_to": 1,
    "assignee_name": "Frodo Baggins",
    "character_quote": "I will take the Ring, though I do not know the way.",
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:00:00Z",
    "completed_at": null
  }
]
```

#### GET /api/quests/{id}
Get quest by ID.

**Response (200):**
```json
{
  "id": 1,
  "title": "Destroy the One Ring",
  "description": "Journey to the fires of Mount Doom...",
  "status": "the_road_goes_ever_on",
  "quest_type": "The Ring",
  "priority": "Critical",
  "is_dark_magic": false,
  "location_id": 6,
  "location_name": "Mordor",
  "assigned_to": 1,
  "assignee_name": "Frodo Baggins",
  "character_quote": "I will take the Ring, though I do not know the way.",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z",
  "completed_at": null
}
```

**Response (404):**
```json
{
  "error": "Quest not found"
}
```

#### POST /api/quests
Create a new quest. Requires authentication.

**Request:**
```json
{
  "title": "Reach Rivendell",
  "description": "Travel to Rivendell to seek counsel from Elrond.",
  "status": "not_yet_begun",
  "quest_type": "The Journey",
  "priority": "Important",
  "is_dark_magic": false,
  "location_id": 2,
  "assigned_to": 1,
  "character_quote": "The Road goes ever on and on..."
}
```

**Response (201):**
```json
{
  "id": 7,
  "title": "Reach Rivendell",
  "description": "Travel to Rivendell to seek counsel from Elrond.",
  "status": "not_yet_begun",
  "quest_type": "The Journey",
  "priority": "Important",
  "is_dark_magic": false,
  "location_id": 2,
  "location_name": "Rivendell",
  "assigned_to": 1,
  "assignee_name": "Frodo Baggins",
  "character_quote": "The Road goes ever on and on...",
  "created_at": "2024-01-15T11:00:00Z",
  "updated_at": "2024-01-15T11:00:00Z",
  "completed_at": null
}
```

**Response (401):**
```json
{
  "error": "Authentication required"
}
```

#### PUT /api/quests/{id}
Update quest. Requires authentication.

**Request:**
```json
{
  "title": "Reach Rivendell",
  "description": "Updated description",
  "status": "the_road_goes_ever_on",
  "quest_type": "The Journey",
  "priority": "Critical",
  "is_dark_magic": false,
  "location_id": 2,
  "assigned_to": 1
}
```

**Response (200):**
```json
{
  "id": 7,
  "title": "Reach Rivendell",
  "description": "Updated description",
  "status": "the_road_goes_ever_on",
  "quest_type": "The Journey",
  "priority": "Critical",
  "is_dark_magic": false,
  "location_id": 2,
  "location_name": "Rivendell",
  "assigned_to": 1,
  "assignee_name": "Frodo Baggins",
  "created_at": "2024-01-15T11:00:00Z",
  "updated_at": "2024-01-15T11:30:00Z",
  "completed_at": null
}
```

#### PUT /api/quests/{id}/complete
Mark quest as complete. Requires authentication.

**Response (200):**
```json
{
  "id": 7,
  "title": "Reach Rivendell",
  "status": "it_is_done",
  "completed_at": "2024-01-15T12:00:00Z",
  "character_quote": "The Road goes ever on and on...",
  "message": "The Quest Is Done!"
}
```

#### DELETE /api/quests/{id}
Delete quest. Requires authentication.

**Response (200):**
```json
{
  "message": "Quest deleted successfully"
}
```

**Response (404):**
```json
{
  "error": "Quest not found"
}
```

### Member Endpoints

#### GET /api/members
Get all Fellowship members.

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "Frodo Baggins",
    "race": "Hobbit",
    "role": "Ring-bearer",
    "status": "active",
    "description": "The brave hobbit who carries the One Ring to Mount Doom.",
    "created_at": "2024-01-15T10:00:00Z"
  }
]
```

#### GET /api/members/{id}
Get member by ID.

**Response (200):**
```json
{
  "id": 1,
  "name": "Frodo Baggins",
  "race": "Hobbit",
  "role": "Ring-bearer",
  "status": "active",
  "description": "The brave hobbit who carries the One Ring to Mount Doom.",
  "created_at": "2024-01-15T10:00:00Z"
}
```

### Location Endpoints

#### GET /api/locations
Get all Middle-earth locations.

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "The Shire",
    "region": "Eriador",
    "description": "The peaceful homeland of the Hobbits.",
    "created_at": "2024-01-15T10:00:00Z"
  }
]
```

#### GET /api/locations/{id}
Get location by ID.

**Response (200):**
```json
{
  "id": 1,
  "name": "The Shire",
  "region": "Eriador",
  "description": "The peaceful homeland of the Hobbits.",
  "created_at": "2024-01-15T10:00:00Z"
}
```

### Health Endpoint

#### GET /api/health
Health check endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T12:00:00Z"
}
```

## How It Works

### Architecture Overview

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ HTTP/HTTPS
       ▼
┌─────────────┐
│   Caddy     │ (Reverse Proxy, Port 80)
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│ Frontend │   │ Backend  │   │ SQLite   │
│  React   │   │  Flask   │   │ Database │
│  :3000   │   │  :5000   │   │ (file)   │
└──────────┘   └──────────┘   └──────────┘
```

### Data Flow

#### Quest Creation Flow
1. User fills out quest form in React frontend
2. Frontend calls `POST /api/quests` with quest data
3. Flask backend validates request and checks authentication
4. Backend creates Quest record in SQLite database
5. Backend returns created quest with all fields
6. Frontend updates UI to show new quest

#### Quest Completion Flow
1. User clicks "Mark Complete" button on quest card
2. Frontend calls `PUT /api/quests/{id}/complete`
3. Backend updates quest status to "it_is_done"
4. Backend sets `completed_at` timestamp
5. Backend returns quest with character quote
6. Frontend displays completion animation and quote
7. Frontend updates journey progress visualization

#### Authentication Flow
1. User enters credentials on login page
2. Frontend calls `POST /api/auth/login`
3. Backend validates credentials against database
4. Backend creates session and sets session cookie
5. Backend returns user data
6. Frontend stores user in state and redirects to dashboard
7. Subsequent API calls include session cookie automatically

### Database Schema

#### Quests Table
```sql
CREATE TABLE quests (
    id INTEGER PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'not_yet_begun',
    quest_type VARCHAR(50),
    priority VARCHAR(20),
    is_dark_magic BOOLEAN DEFAULT 0,
    location_id INTEGER REFERENCES locations(id),
    assigned_to INTEGER REFERENCES users(id),
    character_quote TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
```

#### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### Members Table
```sql
CREATE TABLE members (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    race VARCHAR(50) NOT NULL,
    role VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### Locations Table
```sql
CREATE TABLE locations (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    region VARCHAR(100) NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### State Management

**Frontend State (React)**
- User authentication state (logged in user)
- Quest list (all quests, filtered quests)
- Locations list
- Members list
- UI state (loading, errors, form visibility)

**Backend State (Flask)**
- Session storage (user authentication)
- Database state (SQLite)

### Error Handling

**Frontend Error Handling**
- API errors displayed as user-friendly messages
- Network errors show retry options
- Form validation errors shown inline
- Loading states prevent duplicate submissions

**Backend Error Handling**
- 400 Bad Request: Invalid input data
- 401 Unauthorized: Authentication required
- 404 Not Found: Resource doesn't exist
- 500 Internal Server Error: Server-side error

## Design & UI/UX for LOTR Mood

### Color Palette

#### Primary Colors
- **Parchment**: `#F4E4BC`, `#E8D5B7` - Background, card backgrounds
- **Earth Brown**: `#8B4513`, `#A0522D` - Borders, accents
- **Forest Green**: `#2D5016`, `#3D6B1F` - Success states, nature elements
- **Gold**: `#DAA520`, `#FFD700` - Important elements, completed quests
- **Dark Red**: `#8B0000`, `#A52A2A` - Critical priority, dark magic
- **Deep Blue**: `#1A1F2E`, `#2C3E50` - Headers, dark backgrounds

#### Status Colors
- **Not Yet Begun**: `#6B7280` (Gray) - Neutral, waiting
- **The Road Goes Ever On**: `#F59E0B` (Amber) - Active, journey
- **It Is Done**: `#10B981` (Green) - Success, completion
- **The Shadow Falls**: `#DC2626` (Red) - Blocked, danger

#### Priority Colors
- **Critical**: `#DC2626` (Red) - Urgent, important
- **Important**: `#F59E0B` (Gold) - Significant, notable
- **Standard**: `#6B7280` (Silver/Gray) - Normal, routine

### Typography

#### Font Families
- **Headers**: `'Cinzel'`, `'Uncial Antiqua'`, or `serif` - Epic, medieval feel
- **Body Text**: `'Lora'`, `'Crimson Text'`, or `serif` - Readable, elegant
- **UI Elements**: `'Inter'`, `'Roboto'`, or `sans-serif` - Modern, clear

#### Font Sizes
- **Page Title**: `2.5rem` (40px) - Epic, prominent
- **Section Headers**: `1.875rem` (30px) - Clear hierarchy
- **Quest Titles**: `1.25rem` (20px) - Readable, important
- **Body Text**: `1rem` (16px) - Standard readability
- **Labels**: `0.875rem` (14px) - Secondary information

#### Font Weights
- **Headers**: `700` (Bold) - Strong, epic
- **Quest Titles**: `600` (Semi-bold) - Emphasis
- **Body Text**: `400` (Regular) - Readable
- **Labels**: `400` (Regular) - Subtle

### Visual Design Elements

#### Backgrounds
- **Main Background**: Parchment texture or subtle gradient
- **Card Backgrounds**: Parchment color with subtle shadow
- **Dark Magic Quests**: Dark red gradient with subtle glow

#### Borders & Shadows
- **Card Borders**: `2px solid` earth brown, rounded corners `8px`
- **Card Shadows**: Subtle shadow for depth (`0 2px 8px rgba(0,0,0,0.1)`)
- **Dark Magic Glow**: Red shadow effect (`0 0 10px rgba(220, 38, 38, 0.5)`)

#### Icons & Visual Indicators
- **Quest Type Icons**:
  - The Journey: Compass icon
  - The Battle: Sword icon
  - The Fellowship: Group/people icon
  - The Ring: Ring/circle icon
  - Dark Magic: Eye of Sauron icon
- **Priority Indicators**: Colored rings (red, gold, silver)
- **Status Badges**: Colored badges with LOTR terminology
- **Location Badges**: Middle-earth location names with map pin icon

#### Spacing & Layout
- **Container Padding**: `1.5rem` (24px) - Comfortable spacing
- **Card Padding**: `1.25rem` (20px) - Readable content
- **Element Spacing**: `1rem` (16px) - Consistent rhythm
- **Grid Gaps**: `1.5rem` (24px) - Clear separation

### User Experience Patterns

#### Navigation
- **Top Navigation Bar**: Always visible, LOTR-themed
- **Breadcrumbs**: Show current location in app
- **Back Buttons**: Clear way to return to previous view
- **Menu Items**: LOTR terminology ("The Council Chamber", "The Scrolls")

#### Quest Cards
- **Hover Effects**: Subtle lift and shadow increase
- **Click Targets**: Large, easy to click
- **Visual Hierarchy**: Title prominent, details secondary
- **Status Visibility**: Color-coded badges immediately visible
- **Priority Indicators**: Colored rings draw attention

#### Forms
- **Input Styling**: Parchment-themed inputs with earth brown borders
- **Placeholder Text**: LOTR-themed hints ("Describe the quest in epic detail...")
- **Validation**: Clear error messages with helpful guidance
- **Submit Buttons**: Prominent, epic styling ("Propose Quest", "Revise Quest")

#### Feedback & Interactions
- **Loading States**: Subtle spinner with LOTR-themed message
- **Success Messages**: Epic confirmation ("The Quest Is Done!")
- **Error Messages**: Clear, helpful, non-intimidating
- **Character Quotes**: Displayed prominently on quest completion
- **Animations**: Subtle, epic (fade-in, slide-in, not distracting)

#### Responsive Design
- **Desktop**: Full layout with sidebar navigation
- **Tablet**: Adjusted grid, stacked navigation
- **Mobile**: Single column, bottom navigation

### Accessibility

#### Color Contrast
- **Text on Background**: Minimum 4.5:1 contrast ratio
- **Interactive Elements**: Minimum 3:1 contrast ratio
- **Status Indicators**: Color + text label for colorblind users

#### Keyboard Navigation
- **Tab Order**: Logical flow through interactive elements
- **Focus Indicators**: Clear visual focus states
- **Keyboard Shortcuts**: Common actions accessible via keyboard

#### Screen Readers
- **ARIA Labels**: Descriptive labels for all interactive elements
- **Semantic HTML**: Proper heading hierarchy, landmarks
- **Alt Text**: Descriptive text for all icons and images

### Epic Storytelling Elements

#### Welcome Experience
- **Login Page**: Epic welcome message with LOTR imagery
- **First Visit**: Brief introduction to the Fellowship's journey
- **Character Selection**: Visual character cards (optional enhancement)

#### Quest Descriptions
- **Epic Language**: Use LOTR-style descriptions
- **Story Context**: Connect quests to Middle-earth locations
- **Character Quotes**: Memorable quotes from characters

#### Progress Visualization
- **Journey Map**: Visual progress from Shire to Mordor
- **Milestone Celebrations**: Special messages at key points
- **Completion Rewards**: Character quotes and visual feedback

#### Dark Magic Integration
- **Visual Warnings**: Clear indication of dark magic quests
- **Story Context**: "Sauron's influence has corrupted this quest"
- **Testing Challenge**: Represents infrastructure bugs to fix

### Design Principles

1. **Epic but Simple**: LOTR theme enhances, doesn't complicate
2. **Clear Hierarchy**: Important information stands out
3. **Consistent Theming**: LOTR elements throughout, not just decoration
4. **Accessible**: Usable by all, regardless of ability
5. **Performant**: Fast, smooth interactions
6. **Responsive**: Works on all device sizes
7. **Intuitive**: Easy to understand and use

## Testing Scenarios

### Functional Testing
- User authentication (login, logout, session)
- Quest CRUD operations (create, read, update, delete)
- Quest completion with character quotes
- Filtering and sorting quests
- Dashboard statistics accuracy
- Dark magic quest identification

### UI/UX Testing
- LOTR terminology displayed correctly
- Visual styling matches specification
- Responsive design on different screen sizes
- Accessibility compliance
- Loading and error states

### Dark Magic Testing
- Dark magic quests display with special styling
- Dark magic quests can be filtered
- Dark magic quest completion may fail (simulated bug)
- Dark magic quests appear in dashboard warnings

## Success Metrics

1. **Usability**: Users can complete core tasks (create, complete, filter quests) without confusion
2. **Engagement**: LOTR theme enhances user experience without overwhelming
3. **Performance**: Page loads < 2 seconds, API responses < 500ms
4. **Accessibility**: WCAG 2.1 AA compliance
5. **Test Coverage**: > 80% code coverage
6. **Documentation**: Complete API documentation and user guide

## Azure NPC Chat Specification (Phase 7-8)

### Functional behavior
- NPC chat is available from Dashboard side panel.
- Characters supported: Frodo, Sam, Gandalf.
- NPC initiates first with randomized opener style (question/judgement/reflection).
- User can continue a natural multi-turn conversation.
- NPC always nudges toward a concrete next action in the app.

### API contract
- `POST /api/chat/start`
- `POST /api/chat/message`
- `GET /api/chat/session`
- `POST /api/chat/reset`

Each response includes:
- character
- messages transcript
- suggested_action `{ goal_type, title, reason, target }`

### Security constraints
- Azure AI credentials are backend-only.
- Frontend never receives endpoint keys or deployment secrets.

### MVP memory model
- Conversation memory persists for the user login session only.
- Reset action starts a new opener and clears transcript.

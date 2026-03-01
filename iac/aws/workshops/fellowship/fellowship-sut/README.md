# The Fellowship's Quest List - SUT (System Under Test)

A LOTR-themed todo list application for the Fellowship of the Build tutorial. This application allows Fellowship members to track their epic journey through Middle-earth using a simple, engaging quest list interface.

## Overview

The Fellowship's Quest List is a full-stack web application built with:
- **Backend**: Flask (Python) with REST API and Swagger documentation
- **Frontend**: React with TypeScript
- **Database**: SQLite (for cost efficiency)
- **Reverse Proxy**: Caddy
- **Containerization**: Docker Compose

## Features

- **User Authentication**: Login as Fellowship members (Frodo, Sam, Aragorn, etc.)
- **Quest Management**: Propose, view, revise, and complete quests with epic LOTR terminology
- **Quest Types**: Categorize quests as The Journey, The Battle, The Fellowship, The Ring, or Dark Magic
- **Priority System**: Mark quests as Critical, Important, or Standard with visual indicators
- **Dark Magic Quests**: Special quests corrupted by Sauron's influence (for testing challenges)
- **Character Quotes**: Memorable quotes displayed when quests are completed
- **Fellowship Members**: View member profiles and status
- **Locations**: Track journey through Middle-earth locations
- **The Council Chamber**: Dashboard with LOTR-themed statistics and journey progress
- **The Scrolls of Middle-earth**: Quest list with parchment styling and epic visual design
- **Companion Chat (Azure AI)**: Realistic in-character conversation with Frodo, Sam, or Gandalf
- **Action Nudges**: NPCs guide users toward concrete next steps in quests
- **REST API**: Well-architected API with Swagger documentation

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Port 80 available (or modify nginx configuration)

### Running Locally

1. **Clone or navigate to the directory**:
   ```bash
   cd iac/aws/workshops/fellowship/fellowship-sut
   ```

2. **Start the application**:
   ```bash
   docker compose up -d
   ```

3. **Wait for services to start** (about 30-60 seconds):
   ```bash
   docker compose ps
   ```

4. **Access the application**:
   - Frontend: http://localhost/
   - API Swagger Docs: http://localhost/api/swagger/
   - Health Check: http://localhost/api/health

### Default Credentials

The application comes pre-seeded with Fellowship member accounts:

| Username | Password | Role |
|----------|----------|------|
| frodo_baggins | fellowship123 | Ring-bearer |
| samwise_gamgee | fellowship123 | Companion |
| aragorn | fellowship123 | Ranger |
| legolas | fellowship123 | Archer |
| gimli | fellowship123 | Warrior |
| gandalf | fellowship123 | Guide |

## Architecture

```
┌─────────────┐
│   Internet  │
└──────┬──────┘
       │ Port 80
       ▼
┌─────────────┐
│    Nginx    │ (Reverse Proxy)
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│ Frontend │   │ Backend  │   │ SQLite   │
│  :3000   │   │  :5000   │   │ (file)   │
└──────────┘   └──────────┘   └──────────┘
```

## API Documentation

### Base URL

- Local: `http://localhost/api`
- Production: `http://<ec2-ip>/api`

### Swagger UI

Interactive API documentation is available at:
- http://localhost/api/swagger/

### Endpoints

#### Authentication

- `POST /api/auth/login` - Login user
  ```json
  {
    "username": "frodo_baggins",
    "password": "fellowship123"
  }
  ```

- `POST /api/auth/logout` - Logout user

- `GET /api/auth/me` - Get current user

#### Quests

- `GET /api/quests` - List all quests with optional filtering
  - Query parameters: `status`, `quest_type`, `priority`, `dark_magic`, `location_id`, `assigned_to`
  - Example: `GET /api/quests?status=it_is_done&priority=Critical`
- `GET /api/quests/{id}` - Get quest by ID
- `POST /api/quests` - Propose a new quest (requires auth)
  ```json
  {
    "title": "Destroy the One Ring",
    "description": "Journey to Mount Doom and cast the Ring into the flames.",
    "status": "not_yet_begun",
    "quest_type": "The Ring",
    "priority": "Critical",
    "is_dark_magic": false,
    "character_quote": "I will take the Ring, though I do not know the way.",
    "location_id": 6,
    "assigned_to": 1
  }
  ```
- `PUT /api/quests/{id}` - Revise quest (requires auth)
- `PUT /api/quests/{id}/complete` - Mark quest as complete (The Quest Is Done)
- `DELETE /api/quests/{id}` - Abandon quest (requires auth)

#### Members

- `GET /api/members` - List all Fellowship members
- `GET /api/members/{id}` - Get member by ID

#### Locations

- `GET /api/locations` - List all locations
- `GET /api/locations/{id}` - Get location by ID

#### Health

- `GET /api/health` - Health check endpoint

#### NPC Chat (Azure AI)

- `POST /api/chat/start` - Start chat and receive random opener
- `POST /api/chat/message` - Send user turn and receive NPC response
- `GET /api/chat/session` - Get current session transcript
- `POST /api/chat/reset` - Reset chat session for selected character

### Example API Calls

**Login**:
```bash
curl -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"frodo_baggins","password":"fellowship123"}' \
  -c cookies.txt
```

**Get Quests**:
```bash
curl http://localhost/api/quests
```

**Propose a Quest** (requires authentication):
```bash
curl -X POST http://localhost/api/quests \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "title": "Reach Mount Doom",
    "description": "Journey to Mount Doom to destroy the Ring",
    "status": "the_road_goes_ever_on",
    "quest_type": "The Ring",
    "priority": "Critical",
    "is_dark_magic": false,
    "location_id": 6
  }'
```

**Complete a Quest**:
```bash
curl -X PUT http://localhost/api/quests/1/complete \
  -H "Content-Type: application/json" \
  -b cookies.txt
```

**Filter Dark Magic Quests**:
```bash
curl http://localhost/api/quests?dark_magic=true
```

**Start NPC Chat**:
```bash
curl -X POST http://localhost/api/chat/start \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"character":"gandalf"}'
```

**Send NPC Message**:
```bash
curl -X POST http://localhost/api/chat/message \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"character":"gandalf","message":"What should I do next?"}'
```

## Azure OpenAI Configuration (NPC Chat)

The application uses **Azure OpenAI** to power realistic NPC companions (Frodo, Sam, Gandalf). The Azure credentials are **backend-only** and never exposed to the frontend.

### Prerequisites

1. **Azure Subscription**: You need an active Azure subscription
2. **Azure OpenAI Service**: Deploy an Azure OpenAI resource
3. **Model Deployment**: Deploy a `gpt-4` (or `gpt-4-mini`) model within your resource

### Getting Azure Credentials

1. **Create Azure OpenAI Resource**:
   - Go to [Azure Portal](https://portal.azure.com)
   - Create new resource: "Azure OpenAI"
   - Select region (e.g., East US, West US)
   - Choose Standard pricing tier

2. **Deploy Model**:
   - In your resource, go to "Model deployments"
   - Click "Create new deployment"
   - Choose `gpt-4` or `gpt-4-mini` as model
   - Name your deployment (e.g., `gpt-4-mini`)
   - Accept defaults; proceed to create

3. **Retrieve Credentials**:
   - Go to "Keys and Endpoint" in your resource
   - Copy **Endpoint URL** (e.g., `https://classroom-open-ai.openai.azure.com/`)
   - Copy **API Key 1** (keep secret!)
   - Note your **Deployment Name** (from model deployments)

### Local Development Setup

1. **Export credentials to shell**:
   ```bash
   export AZURE_OPENAI_ENDPOINT=https://classroom-open-ai.openai.azure.com/
   export AZURE_OPENAI_API_KEY=your-actual-api-key-here
   export AZURE_OPENAI_DEPLOYMENT=gpt-4-mini
   export AZURE_OPENAI_API_VERSION=2024-02-15-preview
   ```

2. **Start application**:
   ```bash
   docker-compose up -d
   ```

3. **Verify Azure integration**:
   ```bash
   # Login first
   curl -X POST http://localhost/api/auth/login \
     -H "Content-Type: application/json" \
     -c cookies.txt \
     -d '{"username":"frodo_baggins","password":"fellowship123"}'

   # Start NPC chat (should return in-character opener if Azure is working)
   curl -X POST http://localhost/api/chat/start \
     -H "Content-Type: application/json" \
     -b cookies.txt \
     -d '{"character":"gandalf"}'

   # Expected response includes "opener" field with NPC greeting
   ```

### Behavior Without Azure Credentials

If `AZURE_OPENAI_API_KEY` or `AZURE_OPENAI_ENDPOINT` are empty:

- Chat endpoints return **deterministic fallback responses**
- NPC still engages in-character and suggests actions
- Chat UI remains fully functional
- No errors; graceful degradation

Example fallback:
```
Gandalf: "Clarity first: choose the highest-impact action and execute it now. 
Will you take this next step now: Resolve a dark magic quest?"
```

### Production Deployment

For production environments (AWS EC2, Azure VM, Kubernetes):

1. **Use AWS Secrets Manager or Azure Key Vault**:
   ```bash
   # Example: AWS
   aws secretsmanager create-secret \
     --name fellowship-azure-openai \
     --secret-string '{
       "endpoint":"https://classroom-open-ai.openai.azure.com/",
       "api_key":"your-prod-key",
       "deployment":"gpt-4",
       "api_version":"2024-02-15-preview"
     }'
   ```

2. **Inject at container runtime**:
   ```bash
   # In docker-compose or ECS task definition
   docker-compose up -d \
     -e AZURE_OPENAI_ENDPOINT="$(aws secretsmanager get-secret-value --secret-id fellowship-azure-openai --query SecretString --output text | jq -r '.endpoint')" \
     -e AZURE_OPENAI_API_KEY="$(aws secretsmanager get-secret-value --secret-id fellowship-azure-openai --query SecretString --output text | jq -r '.api_key')"
   ```

3. **Never commit secrets to git**:
   - ✅ DO: Use environment variables or secret managers
   - ❌ DON'T: Hardcode keys in `.env`, `docker-compose.yml`, or code

### Tuning Azure Configuration

**Token & Temperature Settings** (in `sut/backend/config.py`):

```python
AZURE_OPENAI_MAX_TOKENS = 220       # Max response length (tune up for verbosity)
AZURE_OPENAI_TEMPERATURE = 0.85     # Creativity (0=deterministic, 1=random)
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"  # API version
```

- **Max Tokens**: 220 is tuned for concise NPC replies; increase to 300-500 for longer monologues
- **Temperature**: 0.85 gives personality without nonsense; reduce to 0.5 for safer, more predictable replies
- **API Version**: Check [Azure docs](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference) for latest versions

## Testing

### Running Tests

1. **Install test dependencies**:
   ```bash
   pip install -r tests/requirements.txt
   ```

2. **Install Playwright browsers**:
   ```bash
   # Install Firefox (recommended for macOS - more stable)
   playwright install firefox
   
   # Or install Chromium (may crash on some macOS systems)
   playwright install chromium
   
   # Or install all browsers
   playwright install
   ```

3. **Run all tests**:
   ```bash
   pytest
   ```

4. **Run specific test files**:
   ```bash
   pytest tests/test_login.py
   pytest tests/test_dashboard.py
   pytest tests/test_api.py
   ```

5. **Run with markers**:
   ```bash
   pytest -m smoke
   pytest -m api
   pytest -m ui
   pytest -m realstack
   ```

7. **Run real-stack BDD CORS + Login test (Docker Compose, no mocks)**:
   ```bash
   # Uses real frontend, backend and caddy from docker-compose.yml
   pytest tests/test_cors_login_bdd.py -m realstack -v
   ```

6. **Run Behave (Gherkin) tests**:
   ```bash
   cd tests
   behave
   ```

### Release Quality Gate (Required)

Use these commands before marking implementation as complete:

```bash
# From fellowship-sut/ (docker compose must already be up)
pytest tests/test_cors_login_bdd.py tests/test_map_page.py tests/test_npc_chat.py tests/test_npc_chat_api.py -q

# From fellowship-sut/sut/frontend/
npm run test -- test/services/api.chat.test.ts test/store/characterStore.test.ts --run
```

Completion policy: if any command above fails, the feature is not done.
   
   Or run a specific feature:
   ```bash
   behave features/map_page.feature
   ```
   
   **Note**: If Chromium crashes, use Firefox instead:
   ```bash
   BROWSER=firefox behave features/map_page.feature
   ```

### Test Structure

- `tests/test_login.py` - Login functionality tests
- `tests/test_dashboard.py` - Dashboard UI tests
- `tests/test_api.py` - API endpoint tests
- `tests/test_cors_login_bdd.py` - Gherkin/BDD CORS+login real-stack verification
- `tests/page_objects/` - Page Object Model classes for pytest/BDD tests
- `playwright/page_objects/` - Legacy page object classes used by Behave map tests

### Page Object Model

The tests use the Page Object Model pattern:

```python
from tests.page_objects.login_page import LoginPage

login_page = LoginPage(page, base_url)
login_page.login('frodo_baggins', 'fellowship123')
```

## Development

### Project Structure

```
fellowship-sut/
├── docker-compose.yml          # Main orchestration
├── nginx/
│   └── nginx.conf              # Reverse proxy config
├── sut/
│   ├── backend/                # Flask backend
│   │   ├── app.py             # Main application
│   │   ├── models/            # SQLAlchemy models
│   │   ├── routes/             # API routes
│   │   ├── services/          # Business logic
│   │   └── utils/              # Database & seeding
│   └── frontend/               # React frontend
│       └── src/
│           ├── components/    # React components
│           ├── pages/          # Page components
│           └── services/       # API client
├── tests/                      # Playwright tests
├── playwright/
│   └── page_objects/           # Page Object Model
└── README.md
```

### Backend Development

1. **Navigate to backend directory**:
   ```bash
   cd sut/backend
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Flask development server**:
   ```bash
   export FLASK_APP=app.py
   export FLASK_ENV=development
   python app.py
   ```

### Frontend Development

1. **Navigate to frontend directory**:
   ```bash
   cd sut/frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Run development server**:
   ```bash
   npm start
   ```

### Database

The SQLite database is automatically created and seeded on first startup. The database file is stored in:
- Docker volume: `/app/data/fellowship.db`
- Local development: `sut/backend/data/fellowship.db`

To reset the database:
```bash
docker compose down -v
docker compose up -d
```

## Deployment

### EC2 Deployment (Automatic)

The SUT is automatically deployed on EC2 instances when setting up a fellowship classroom:

1. **During Classroom Setup**: When you run `setup_classroom.sh` with `--workshop fellowship`, the script:
   - Creates an S3 bucket for the SUT files
   - Packages the `fellowship-sut` directory into a tarball
   - Uploads the tarball to S3
   - Configures EC2 IAM roles with S3 access permissions

2. **During EC2 Instance Provisioning**: The `user_data.sh` script:
   - Downloads the SUT tarball from S3
   - Extracts it to `/home/ec2-user/fellowship-sut`
   - Starts all services via Docker Compose
   - Exposes the application on port 80

**No manual steps required** - the SUT is automatically available on all provisioned EC2 instances.

### Manual Deployment (For Testing)

If you need to manually deploy the SUT to an existing EC2 instance:

1. **Copy files to EC2 instance**:
   ```bash
   scp -r fellowship-sut/ ec2-user@<ec2-ip>:~/
   ```

2. **SSH into instance**:
   ```bash
   ssh ec2-user@<ec2-ip>
   ```

3. **Start services**:
   ```bash
   cd ~/fellowship-sut
   docker compose up -d
   ```

4. **Check status**:
   ```bash
   docker compose ps
   docker compose logs -f
   ```

## Troubleshooting

### Services not starting

1. **Check Docker Compose logs**:
   ```bash
   docker compose logs
   ```

2. **Check individual service logs**:
   ```bash
   docker compose logs backend
   docker compose logs frontend
   docker compose logs nginx
   ```

3. **Verify ports are available**:
   ```bash
   netstat -tulpn | grep -E ':(80|3000|5000)'
   ```

### Database issues

1. **Reset database**:
   ```bash
   docker compose down -v
   docker compose up -d
   ```

2. **Check database file**:
   ```bash
   docker compose exec backend ls -la /app/data/
   ```

### Frontend not loading

1. **Check if frontend is built**:
   ```bash
   docker compose exec frontend ls -la /usr/share/nginx/html
   ```

2. **Rebuild frontend**:
   ```bash
   docker compose up -d --build frontend
   ```

### API not responding

1. **Check backend health**:
   ```bash
   curl http://localhost/api/health
   ```

2. **Check backend logs**:
   ```bash
   docker compose logs backend
   ```

## LOTR Theme

### Fellowship Members

- **Frodo Baggins** - Hobbit, Ring-bearer
- **Samwise Gamgee** - Hobbit, Companion
- **Aragorn** - Human, Ranger
- **Legolas** - Elf, Archer
- **Gimli** - Dwarf, Warrior
- **Gandalf** - Wizard, Guide

### Quest Types

- **The Journey** 🧭 - Travel and navigation quests
- **The Battle** ⚔️ - Combat and defense quests
- **The Fellowship** 👥 - Team and rescue quests
- **The Ring** 💍 - Ring-related quests
- **Dark Magic** 👁️ - Quests corrupted by Sauron's influence (for testing challenges)

### Quest Priorities

- **Critical** 🔴 - Urgent quests that determine the fate of Middle-earth
- **Important** 🟡 - Significant quests that advance the journey
- **Standard** ⚪ - Routine quests and tasks

### Quest Status (LOTR Terminology)

- **Not Yet Begun** - Quest has been proposed but not started
- **The Road Goes Ever On...** - Quest is in progress
- **It Is Done** - Quest has been completed
- **The Shadow Falls** - Quest is blocked or corrupted

### Sample Quests

- **Destroy the One Ring** (The Ring, Critical) - Journey to Mount Doom and cast the Ring into the flames
- **Reach Rivendell** (The Journey, Important) - Travel to Rivendell to seek counsel from Elrond
- **Escape from Moria** (The Battle, Critical) - Survive the dangers of the ancient Dwarven kingdom
- **Fix the Broken Bridge** (Dark Magic, Critical) - Sauron's dark magic has corrupted the bridge
- **Rescue Merry and Pippin** (The Fellowship, Important) - Rescue the captured Hobbits

### Locations

- **The Shire** (Eriador) - The peaceful homeland of the Hobbits
- **Rivendell** (Eriador) - The Last Homely House, home of Elrond
- **Moria** (Misty Mountains) - The ancient Dwarven kingdom, now overrun by darkness
- **Lothlórien** (Rhovanion) - The Golden Wood, realm of Galadriel and Celeborn
- **Rohan** (Rhovanion) - The land of the Horse-lords
- **Mordor** (Mordor) - The dark land of Sauron, where the One Ring was forged

### Dark Magic Quests

Dark Magic quests represent infrastructure bugs and testing challenges. They:
- Display with special red/dark styling and Eye of Sauron icon
- May appear/disappear randomly (simulated bug)
- May fail to complete (simulated bug)
- Appear in dashboard warnings
- Can be filtered via API: `GET /api/quests?dark_magic=true`

## Contributing

This is a tutorial SUT application. For issues or improvements, please refer to the main Fellowship tutorial documentation.

## Azure AI Setup (Optional, backend-only)

Set these environment variables for backend service:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION` (default: `2024-02-15-preview`)

If these are missing, the NPC chat still works using deterministic in-character fallback responses.

## License

Part of the Fellowship of the Build tutorial - TestingFantasy

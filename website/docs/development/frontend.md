---
sidebar_position: 2
---

# Frontend Documentation

## React Application Structure

The frontend is a React Single Page Application (SPA) built with Vite and deployed to S3/CloudFront.

**Directory Structure:**
```
frontend/ec2-manager/
├── src/
│   ├── pages/                    # Page components
│   │   ├── Landing.jsx          # Landing page
│   │   ├── Login.jsx            # Login page
│   │   ├── WorkshopDashboard.jsx # Main dashboard
│   │   ├── WorkshopConfig.jsx   # Workshop configuration
│   │   ├── TutorialDashboard.jsx # Tutorial session dashboard
│   │   └── TutorialSessionForm.jsx # Create/edit sessions
│   ├── components/               # Reusable components
│   │   ├── Header.jsx           # Navigation header
│   │   └── SettingsModal.jsx   # Settings modal
│   ├── services/                # API and authentication
│   │   ├── api.js               # API client
│   │   └── auth.jsx             # Authentication context
│   ├── App.jsx                  # Main app component
│   └── index.jsx                # Entry point
├── package.json                 # Dependencies
├── vite.config.js              # Vite configuration
└── README.md                    # Frontend-specific docs
```

## Local Development

1. **Install Dependencies:**
   ```bash
   cd frontend/ec2-manager
   npm install
   ```

2. **Run Development Server:**
   ```bash
   npm run dev
   ```
   The app will be available at `http://localhost:5173`

3. **Build for Production:**
   ```bash
   npm run build
   ```
   Creates optimized production build in `dist/` directory

## Frontend Features

**Pages:**
- **Landing**: Welcome page with project information
- **Login**: Password-based authentication
- **Workshop Dashboard**: Main interface for managing instances
  - View all instances (pool, admin, assigned)
  - Create new instances
  - Assign instances to students
  - Enable/disable HTTPS
  - Delete instances
- **Workshop Config**: Configure workshop templates and settings
- **Tutorial Dashboard**: Manage tutorial sessions
- **Tutorial Session Form**: Create and edit tutorial sessions

**Components:**
- **Header**: Navigation and branding
- **Settings Modal**: Configure timeout settings

**Services:**
- **API Client** (`api.js`): Handles all API requests
  - Automatic password injection
  - Error handling
  - CORS support
- **Authentication** (`auth.jsx`): Manages authentication state
  - Session storage for password
  - Automatic authentication check
  - Login/logout functionality

## Environment Variables

**Build-time Variables:**
- `VITE_API_URL`: API base URL (default: `/api` for relative paths)
  - Production: `https://ec2-management-api-{environment}.testingfantasy.com/api`
  - Development: `/api` (proxied through Vite dev server)

**Example Build:**
```bash
export VITE_API_URL="https://ec2-management-api-dev.testingfantasy.com/api"
npm run build
```

## Deployment

The frontend is automatically deployed during infrastructure setup. Manual deployment:

```bash
./scripts/build_frontend.sh --environment dev --region eu-west-1
```

**Deployment Process:**
1. Builds React application with production optimizations
2. Uploads static files to S3 bucket
3. Sets appropriate cache headers (immutable for assets, no-cache for HTML)
4. Invalidates CloudFront cache

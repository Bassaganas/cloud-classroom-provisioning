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

### Option 1: Test with Existing Deployed Lambda (Recommended)

If you already have infrastructure deployed, test the frontend locally against the real Lambda API.

**Quick Start:**
```bash
./scripts/test_local.sh
```

Choose option 2 when prompted to use the real Lambda API. The script will automatically detect the Lambda URL from Terraform outputs.

**Manual Steps:**

1. **Get the Lambda URL from Terraform**:
   ```bash
   cd iac/aws
   export LAMBDA_URL=$(terraform output -raw instance_manager_url)
   ```

2. **Install frontend dependencies**:
   ```bash
   cd frontend/ec2-manager
   npm install
   ```

3. **Start the dev server**:
   ```bash
   LAMBDA_URL=$LAMBDA_URL npm run dev
   ```

4. **Open browser**: http://localhost:5173

The Vite dev server will proxy all `/api/*` requests to your Lambda URL.

### Option 2: Local Mock API Server

If you don't have infrastructure deployed yet, use a local mock API server.

1. **Install frontend dependencies**:
   ```bash
   cd frontend/ec2-manager
   npm install
   ```

2. **Start the mock API server** (in a separate terminal):
   ```bash
   ./scripts/test_local.sh
   # Choose option 1 for mock API
   ```

3. **Start the React dev server**:
   ```bash
   cd frontend/ec2-manager
   npm run dev
   ```

The app will be available at `http://localhost:5173`

### Option 3: Basic Development Server

For simple frontend-only development:

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

## Testing Checklist

When testing locally, verify:
- [ ] Login page loads
- [ ] Can login with password
- [ ] Landing page shows workshops
- [ ] Can navigate to workshop dashboard
- [ ] Can view instances list
- [ ] Can create pool instances
- [ ] Can create admin instances
- [ ] Can assign instances
- [ ] Can delete instances
- [ ] Can configure timeout settings
- [ ] All API calls work correctly

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

## Local Testing Before Deployment

### Prerequisites

1. **AWS Infrastructure Deployed**: The common infrastructure must be deployed first
2. **Node.js 18+**: For building the React app
3. **AWS CLI Configured**: For uploading to S3

### Step-by-Step Local Testing

1. **Install Dependencies**:
   ```bash
   cd frontend/ec2-manager
   npm install
   ```

2. **Get Lambda URL**:
   ```bash
   # Get Lambda URL from Terraform outputs
   cd iac/aws
   export LAMBDA_URL=$(terraform output -raw instance_manager_url)
   ```

   Or use the automated test script:
   ```bash
   ./scripts/test_local.sh
   # Choose option 2 to use real Lambda API
   ```

3. **Start Dev Server**:
   ```bash
   cd frontend/ec2-manager
   LAMBDA_URL=$LAMBDA_URL npm run dev
   ```

   The Vite dev server will:
   - Start on http://localhost:5173
   - Proxy `/api/*` requests to the Lambda URL

4. **Test the Application**:
   - Open http://localhost:5173
   - You should see the login page
   - Enter the password (from AWS Secrets Manager)
   - Should redirect to the landing page with workshops

## Troubleshooting Local Development

### CORS Errors
- The Lambda should have CORS headers (already implemented)
- Check browser console for specific errors

### 404 on API Calls
- Verify Lambda URL is correct
- Check that `/api` prefix is being used
- Verify Vite proxy is configured correctly

### Login Not Working
- Check that password is correct (from AWS Secrets Manager)
- Verify Lambda `/api/login` endpoint is working
- Test directly: `curl -X POST "$LAMBDA_URL/api/login" -d '{"password":"your-password"}'`

### Lambda URL Not Found
- Make sure infrastructure is deployed: `./scripts/setup_classroom.sh --name <name> --cloud aws --region <region>`
- Check Terraform outputs: `cd iac/aws && terraform output`
- Verify `iac/aws` has been initialized: `terraform init`
- Use the automated test script: `./scripts/test_local.sh` (it handles this automatically)

### Frontend Not Updating After Deployment
- Rebuild and redeploy frontend:
  ```bash
  ./scripts/build_frontend.sh --environment dev --region eu-west-3
  ```
- Clear CloudFront cache (if using custom domain):
  - Go to AWS Console → CloudFront
  - Select your distribution
  - Click "Invalidations" → "Create invalidation"
  - Enter `/*` and create

### 404 on Routes
- CloudFront should have custom error responses (404 → index.html)
- Verify `default_root_object = "index.html"` in CloudFront
- Check S3 bucket has `index.html` uploaded

### API Endpoints Not Working
- Verify Lambda function is deployed with updated code
- Check Lambda logs in CloudWatch
- Test Lambda URL directly: `curl $LAMBDA_URL/api/templates`

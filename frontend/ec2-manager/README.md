# EC2 Instance Manager Frontend

React SPA for managing EC2 classroom instances.

## Local Development

### Prerequisites

- Node.js 18+ and npm
- AWS infrastructure deployed (to get Lambda URL)

### Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Start development server** (easiest):
   ```bash
   # From project root
   ./scripts/test_local.sh
   # Choose option 2 to use real Lambda API
   ```

   Or manually:
   ```bash
   # Get Lambda URL from Terraform
   cd ../../iac/aws/common
   export LAMBDA_URL=$(terraform output -raw instance_manager_url)
   cd ../../frontend/ec2-manager
   npm run dev
   ```

4. **Open browser**: http://localhost:5173

The Vite dev server will proxy `/api/*` requests to the Lambda Function URL.

### Manual API Testing

If you want to test the API directly:

```bash
# Get Lambda URL from Terraform
cd ../../iac/aws/common
LAMBDA_URL=$(terraform output -raw instance_manager_url)

# Test login
curl -X POST "$LAMBDA_URL/api/login" \
  -H "Content-Type: application/json" \
  -d '{"password":"your-password"}'

# Test templates endpoint
curl "$LAMBDA_URL/api/templates"
```

## Building for Production

```bash
npm run build
```

This creates a `dist/` directory with the production build.

## Deployment

Use the build script from the project root:

```bash
./scripts/build_frontend.sh --cloud aws --environment dev
```

This will:
1. Build the React app
2. Upload to S3
3. Invalidate CloudFront cache

## Project Structure

```
src/
  pages/
    Landing.jsx          # Workshop list
    WorkshopDashboard.jsx # Instance management
    WorkshopConfig.jsx    # Timeout settings
    Login.jsx            # Authentication
  services/
    api.js              # API client
    auth.jsx            # Authentication context
  App.jsx               # Router setup
  index.jsx             # Entry point
```

# Mock API Server

A mock API server for local frontend development that simulates the EC2 Instance Manager backend API.

## Quick Start

1. **Install dependencies:**
   ```bash
   cd mock-server
   npm install
   ```

2. **Start the mock server:**
   ```bash
   npm start
   ```

   Or for development with auto-reload:
   ```bash
   npm run dev
   ```

3. **In a separate terminal, start the frontend:**
   ```bash
   cd ..
   npm run dev
   ```

The frontend will automatically proxy API requests to the mock server running on `http://localhost:3001`.

## Default Credentials

- **Password**: `test123`

You can use this password when logging into the frontend application.

## API Endpoints

The mock server implements all backend endpoints:

### Authentication
- `POST /api/login` - Authenticate with password

### Instances
- `GET /api/list` - List all instances
- `POST /api/create` - Create new instances
- `POST /api/assign` - Assign instance to student
- `POST /api/delete` - Delete instance(s)
- `POST /api/enable_https` - Enable HTTPS for instance
- `POST /api/delete_https` - Delete HTTPS for instance
- `POST /api/update_cleanup_days` - Update cleanup days
- `POST /api/bulk_delete` - Bulk delete instances

### Settings
- `GET /api/timeout_settings` - Get timeout settings
- `POST /api/update_timeout_settings` - Update timeout settings

### Workshop Templates
- `GET /api/templates` - Get workshop templates

### Tutorial Sessions
- `POST /api/create_tutorial_session` - Create new tutorial session
- `GET /api/tutorial_sessions` - Get tutorial sessions for workshop
- `GET /api/tutorial_session/:sessionId` - Get specific tutorial session
- `DELETE /api/tutorial_session/:sessionId` - Delete tutorial session

## Mock Data

The server comes pre-loaded with sample data:

- **Workshops**: `fellowship`, `testus_patronus`
- **Instances**: Mix of running, stopped, pool, and admin instances
- **Tutorial Sessions**: Sample sessions for each workshop

All data is stored in-memory and resets when the server restarts.

## Customization

### Change Default Password

Edit `mock-server/mockData.js`:
```javascript
export const MOCK_PASSWORD = 'your-password-here'
```

### Modify Mock Data

Edit `mock-server/mockData.js` to customize:
- Workshop templates
- Initial instances
- Tutorial sessions
- Timeout settings

### Change Port

Set the `PORT` environment variable:
```bash
PORT=4000 npm start
```

Or modify the default in `mock-server/server.js`:
```javascript
const PORT = process.env.PORT || 4000
```

## Using Real API Instead

To use the real API instead of the mock server:

1. Set the `VITE_API_URL` environment variable:
   ```bash
   VITE_API_URL=https://ec2-management-api-dev.testingfantasy.com/api npm run dev
   ```

2. Or update `vite.config.js` to set `LAMBDA_URL`:
   ```bash
   LAMBDA_URL=https://your-lambda-url npm run dev
   ```

## Troubleshooting

### Port Already in Use

If port 3001 is already in use, change it:
```bash
PORT=3002 npm start
```

Then update `vite.config.js` to proxy to the new port.

### CORS Errors

The mock server includes CORS headers. If you see CORS errors, ensure:
- The mock server is running
- The frontend is proxying to the correct port
- No browser extensions are blocking requests

### Data Not Persisting

The mock server uses in-memory storage. All data resets when the server restarts. This is intentional for development purposes.

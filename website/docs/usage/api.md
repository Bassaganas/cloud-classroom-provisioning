---
sidebar_position: 3
---

# API Documentation

:::important
This API documentation describes the **Instance Manager API**, which is **instructor-only** and provides REST endpoints for managing EC2 instances.

**Workshop Lambda functions** (e.g., `classroom_user_management.py` in `functions/aws/testus_patronus/`) serve **HTML pages directly** to students, not REST APIs. Students access these via workshop-specific domains like `testus-patronus.testingfantasy.com` and receive HTML pages with their credentials and instance information.
:::

## Instance Manager API

The Instance Manager API provides RESTful endpoints for managing EC2 instances, tutorial sessions, and configurations. This API is used by the EC2 Manager React frontend and is intended for instructor/admin use only.

### Base URLs

- API Gateway: `https://ec2-management-api-{environment}.testingfantasy.com/api`
- Lambda Function URL: `https://{function-id}.lambda-url.{region}.on.aws/api`

### Authentication

Most endpoints require password authentication via:
- Query parameter: `?password=YOUR_PASSWORD` (GET requests)
- Request body: `{"password": "YOUR_PASSWORD"}` (POST requests)

## Endpoints

### Health Check

```http
GET /api/health
```

**Description:** Check if the API is healthy (no authentication required)

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00Z",
  "environment": "dev",
  "workshop_name": "testus_patronus",
  "region": "eu-west-1",
  "message": "Instance Manager API is healthy"
}
```

### Login

```http
POST /api/login
Content-Type: application/json

{
  "password": "YOUR_PASSWORD"
}
```

**Description:** Authenticate with password (no authentication required for this endpoint)

**Response:**
```json
{
  "success": true,
  "message": "Authentication successful"
}
```

### List Instances

```http
GET /api/list?password=YOUR_PASSWORD&include_terminated=false
```

**Description:** List all EC2 instances (requires authentication)

**Query Parameters:**
- `password` (required): Authentication password
- `include_terminated` (optional): Include terminated instances (default: false)

### Create Instances

```http
POST /api/create
Content-Type: application/json

{
  "password": "YOUR_PASSWORD",
  "workshop_name": "testus_patronus",
  "instance_type": "t3.small",
  "count": 1
}
```

**Description:** Create new EC2 instances (requires authentication)

### Assign Instance

```http
POST /api/assign
Content-Type: application/json

{
  "password": "YOUR_PASSWORD",
  "instance_id": "i-1234567890abcdef0",
  "student_name": "student-001"
}
```

**Description:** Assign an EC2 instance to a student (requires authentication)

### Delete Instances

```http
POST /api/delete
Content-Type: application/json

{
  "password": "YOUR_PASSWORD",
  "instance_ids": ["i-1234567890abcdef0"]
}
```

**Description:** Delete one or more EC2 instances (requires authentication)

### Enable HTTPS

```http
POST /api/enable_https
Content-Type: application/json

{
  "password": "YOUR_PASSWORD",
  "instance_id": "i-1234567890abcdef0",
  "workshop_name": "testus_patronus"
}
```

**Description:** Enable HTTPS access for an EC2 instance via ALB (requires authentication)

### OpenAPI Specification

The API provides an OpenAPI/Swagger specification:

```http
GET /api/swagger.json
```

Access the specification at: `https://ec2-management-api-{environment}.testingfantasy.com/api/swagger.json`

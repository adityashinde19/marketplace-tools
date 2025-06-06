# Marketplace API Documentation

This document provides detailed information about the marketplace API endpoints for managing containerized tools.

## Base URL
All endpoints are prefixed with `/agentbuilder/api/v1/tools_studio/marketplace_tools/`

## API Endpoints

### 1. Fetch All Marketplace Tools
**Endpoint:** `GET /fetch_all_marketplace_tools`

**Description:** Retrieves all available tools from the marketplace with their associated images.

**Response:**
```json
{
    "tools": [
        {
            "tool_id": "string",
            "admin_id": int,
            "name": "string",
            "description": "string",
            "creds_schema": "string",
            "sha": "string",
            "tool_details": "string",
            "soft_delete": "string",
            "api_instruction": "string",
            "image_base64": "base64_encoded_string"
        }
    ]
}
```

### 2. Deploy Tool Container
**Endpoint:** `POST /deploy_tool_container`

**Request Body:**
```json
{
    "user_id": int,
    "tool_id": "string",
    "name": "string",
    "description": "string",
    "details": "string",
    "sha": "string" (optional),
    "credentials": {
        "key1": "value1",
        "key2": "value2"
    }
}
```

**Response:**
```json
{
    "deployment_id": "string",
    "run_id": int,
    "url": "string",
    "status": "string",
    "error": "string" (optional)
}
```

### 3. Update Tool Container
**Endpoint:** `POST /update_tool_container`

**Request Body:**
```json
{
    "deployment_id": "string",
    "config_type": "environment" | "secrets",
    "key_name": "string",
    "key_value": "string",
    "is_secret": boolean,
    "user_id": int
}
```

**Response:**
```json
{
    "status": "success",
    "result": {
        "status": "string",
        "error": "string" (optional)
    }
}
```

### 4. Stop Tool Container
**Endpoint:** `POST /stop_tool_container`

**Request Body:**
```json
{
    "app_name": "string",
    "user_id": int (optional)
}
```

**Response:**
```json
{
    "status": "success",
    "result": {
        "status": "string",
        "error": "string" (optional)
    }
}
```

### 5. Restart Tool Container
**Endpoint:** `POST /restart_tool_container`

**Request Body:**
```json
{
    "app_name": "string",
    "user_id": int (optional)
}
```

**Response:**
```json
{
    "status": "success",
    "result": {
        "status": "string",
        "error": "string" (optional)
    }
}
```

### 6. Delete Tool Container
**Endpoint:** `POST /delete_tool_container`

**Request Body:**
```json
{
    "app_name": "string",
    "user_id": int (optional)
}
```

**Response:**
```json
{
    "status": "success",
    "result": {
        "status": "string",
        "error": "string" (optional)
    }
}

### 7. Get User Tools
**Endpoint:** `POST /get_user_tools`

**Request Body:**
```json
{
    "user_id": int
}
```

**Response:**
```json
{
    "success": boolean,
    "tools": [
        {
            "name": "string",
            "description": "string",
            "image": "base64_encoded_string"
        }
    ],
    "message": "string"
}
```

## Error Handling
All endpoints return appropriate HTTP status codes:
- 200: Success
- 400: Bad Request (invalid input)
- 404: Not Found
- 500: Internal Server Error

## Authentication
The API requires appropriate authentication tokens for accessing protected endpoints.

## Workflow Managers
The API utilizes several workflow managers for different operations:
- `GitHubDeployWorkflowManager`: For deploying new tools
- `GitHubStopWorkflowManager`: For stopping tools
- `GitHubUpdateWorkflowManager`: For updating tool configurations
- `GitHubRestartWorkflowManager`: For restarting tools
- `GitHubDeleteWorkflowManager`: For deleting tools

## Database Operations
The API maintains a database for tracking deployments and updates:
- Stores deployment information
- Tracks container app status
- Maintains user associations
- Records workflow run IDs and URLs

## Best Practices
1. Always validate user IDs when provided
2. Use unique IDs for tracking operations
3. Handle errors gracefully with appropriate logging
4. Update database status after successful operations
5. Use appropriate headers and authentication tokens

## Error Responses
All error responses include a descriptive error message and appropriate HTTP status code.

## Security
- All sensitive data (credentials, tokens) should be properly encrypted
- User IDs are optional but recommended for tracking
- Proper validation of input parameters
- Secure handling of GitHub tokens and repository information

## Monitoring
The API includes logging capabilities for:
- Operation status tracking
- Error monitoring
- Workflow progress
- Database operations

# Async Council API Usage

## Overview

The async API allows you to start long-running council sessions and poll for results, rather than maintaining a single streaming connection.

## Endpoints

### 1. Start Async Council Session
**POST** `/council/start`

Start a council session asynchronously and immediately receive an operation ID.

**Request Body:**
```json
{
  "problem": "What is the best approach to implement feature X?",
  "context": "We are building a web application...",
  "metadata": [
    {"key": "priority", "value": "high"}
  ],
  "num_members": 3,
  "timeout_seconds": 120.0,
  "room_type": "original"
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "created_at": "2025-12-30T10:30:00",
  "updated_at": "2025-12-30T10:30:00",
  "events": [],
  "deliverable": null,
  "error": null
}
```

### 2. Get Operation Status
**GET** `/council/operations/{operation_id}`

Query the status of an async operation and retrieve new events since the last query.

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "created_at": "2025-12-30T10:30:00",
  "updated_at": "2025-12-30T10:30:15",
  "events": [
    {
      "type": "member_joined",
      "payload": {"member_id": "agent_1"}
    },
    {
      "type": "discussion_started",
      "payload": {"topic": "feature implementation"}
    }
  ],
  "deliverable": null,
  "error": null
}
```

When complete:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2025-12-30T10:30:00",
  "updated_at": "2025-12-30T10:32:00",
  "events": [...],
  "deliverable": "# Problem\n\n...\n\n# Deliverable\n\n...",
  "error": null
}
```

### 3. Cancel Operation
**POST** `/council/operations/{operation_id}/cancel`

Cancel a running operation.

**Response:**
```json
{
  "status": "cancelled",
  "operation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Operation Status Values

- `pending`: Operation created but not yet started
- `running`: Council session is actively running
- `completed`: Session completed successfully
- `failed`: Session failed with an error
- `cancelled`: Session was cancelled

## Usage Pattern

### Polling Pattern

```python
import requests
import time

# 1. Start async operation
response = requests.post("http://localhost:8080/council/start", json={
    "problem": "How to optimize our database queries?",
    "num_members": 3,
    "timeout_seconds": 120.0
})
operation = response.json()
operation_id = operation["id"]

# 2. Poll for status
while True:
    response = requests.get(f"http://localhost:8080/council/operations/{operation_id}")
    operation = response.json()
    
    # Process new events
    for event in operation["events"]:
        print(f"Event: {event['type']}")
    
    # Check if complete
    if operation["status"] in ["completed", "failed", "cancelled"]:
        if operation["status"] == "completed":
            print(f"Deliverable:\n{operation['deliverable']}")
        elif operation["status"] == "failed":
            print(f"Error: {operation['error']}")
        break
    
    time.sleep(2)  # Poll every 2 seconds
```

### JavaScript Example

```javascript
async function runAsyncCouncil(problem) {
  // Start operation
  const startResponse = await fetch('http://localhost:8080/council/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ problem, num_members: 3 })
  });
  const { id } = await startResponse.json();
  
  // Poll for completion
  while (true) {
    const statusResponse = await fetch(`http://localhost:8080/council/operations/${id}`);
    const operation = await statusResponse.json();
    
    // Handle events
    operation.events.forEach(event => {
      console.log(`Event: ${event.type}`, event.payload);
    });
    
    // Check completion
    if (['completed', 'failed', 'cancelled'].includes(operation.status)) {
      if (operation.status === 'completed') {
        console.log('Deliverable:', operation.deliverable);
      }
      break;
    }
    
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
}
```

## Notes

- Events are returned incrementally - each query returns only new events since the last query
- Events are buffered in memory, so it's recommended to poll regularly to avoid memory buildup
- Once an operation reaches a terminal state (`completed`, `failed`, `cancelled`), the deliverable is available in the response
- Tasks are automatically cleaned up from internal tracking when they complete or are cancelled
- Operations remain queryable even after task completion, allowing you to retrieve the final result and events

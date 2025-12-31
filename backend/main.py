"""FastAPI backend for LLM Council."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.primitives.problem_definition import ProblemDefinition
from backend.primitives.problem_metadata import Metadata
from backend.services.council_service import CouncilService
from backend.services.memory_buffer_subscriber import MemoryBufferSubscriber
from backend.services.async_operation_service import AsyncOperationService, OperationStatus
from backend.rooms.telemetry.room_event import RoomEvent
from backend.primitives.deliverable import Deliverable

logger = logging.getLogger(__name__)

class ProblemMetadataModel(BaseModel):
    key: str
    value: str


class CouncilRequest(BaseModel):
    problem: str = Field(..., description="Primary problem statement")
    context: str | None = Field(default=None, description="Optional background context")
    metadata: List[ProblemMetadataModel] = Field(default_factory=list)
    num_members: int = Field(default=3, ge=1, le=10)
    timeout_seconds: float = Field(default=120.0, gt=0)
    room_type: str = Field(default="original")


class RoomEventModel(BaseModel):
    type: str
    payload: Dict[str, Any]


class AsyncOperationResponse(BaseModel):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    events: List[RoomEventModel] = Field(default_factory=list)
    deliverable: Optional[str] = None
    error: Optional[str] = None


app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_COUNCIL_SERVICE = CouncilService()
_ASYNC_OPERATION_SERVICE = AsyncOperationService()
_SUPPORTED_ROOM_TYPES = {"original", "round_robin"}


@app.get("/")
async def root() -> Dict[str, Any]:
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}

@app.post("/council/run", response_class=StreamingResponse)
async def run_council(request: CouncilRequest) -> StreamingResponse:
    """Run a full council session and stream events followed by the deliverable."""

    problem_definition = _build_problem_definition(request)
    subscriber = MemoryBufferSubscriber()
    
    logger.info("Starting council session of room type '%s' with %d members", request.room_type, request.num_members)

    _validate_room_type(request.room_type)

    session_task = asyncio.create_task(
        _COUNCIL_SERVICE.run_council_session(
            problem=problem_definition,
            num_of_members=request.num_members,
            timeout=request.timeout_seconds,
            subscriber=subscriber,
            room_type=request.room_type,
        ))

    async def event_stream() -> AsyncIterator[str]:
        poll_interval = 0.5
        try:
            while True:
                events = await subscriber.read_and_flush()
                for event in events:
                    payload = {
                        "kind": "room_event",
                        "event": _serialize_room_event(event),
                    }
                    yield json.dumps(payload) + "\n"

                if session_task.done():
                    try: 
                        deliverable: Deliverable = await session_task
                    except Exception as exc:
                        error_payload = {"kind": "error", "detail": str(exc)}
                        yield json.dumps(error_payload) + "\n"
                        break
                    result_payload = {
                        "kind": "deliverable",
                        "deliverable": deliverable.to_deliverable_string(),
                    }
                    yield json.dumps(result_payload) + "\n"
                    break

                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            if not session_task.done():
                session_task.cancel()
                with suppress(Exception):
                    await session_task
            raise
        except Exception as exc:
            if not session_task.done():
                session_task.cancel()
                with suppress(Exception):
                    await session_task
            error_payload = {"kind": "error", "detail": str(exc)}
            yield json.dumps(error_payload) + "\n"
        finally:
            # Drain any remaining events after completion
            remaining = await subscriber.read_and_flush()
            for event in remaining:
                payload = {
                    "kind": "room_event",
                    "event": _serialize_room_event(event),
                }
                yield json.dumps(payload) + "\n"

    return StreamingResponse(event_stream(), media_type="application/json")

@app.post("/council/start", response_model=AsyncOperationResponse)
async def run_council_async(request: CouncilRequest) -> AsyncOperationResponse:
    """Start a council session asynchronously and return operation ID."""
    
    problem_definition = _build_problem_definition(request)
    _validate_room_type(request.room_type)
    
    # Create operation
    operation_id = await _ASYNC_OPERATION_SERVICE.create_operation()
    subscriber = _ASYNC_OPERATION_SERVICE.get_subscriber(operation_id)
    
    if subscriber is None:
        raise HTTPException(status_code=500, detail="Failed to create operation subscriber")
    
    try:
        # Start council session
        session_task = asyncio.create_task(
            _COUNCIL_SERVICE.run_council_session(
                problem=problem_definition,
                num_of_members=request.num_members,
                timeout=request.timeout_seconds,
                subscriber=subscriber,
                room_type=request.room_type))

        # Register task with operation service
        await _ASYNC_OPERATION_SERVICE.register_task(operation_id, session_task)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    
    # Return operation info
    operation = await _ASYNC_OPERATION_SERVICE.get_operation(operation_id)
    if operation is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve operation")
    
    return AsyncOperationResponse(
        id=operation.id,
        status=operation.status.value,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
        events=[],
        deliverable=None,
        error=operation.error,
    )

@app.get("/council/operations/{operation_id}", response_model=AsyncOperationResponse)
async def get_operation_status(operation_id: str) -> AsyncOperationResponse:
    """Get the status and latest events for an async operation."""
    
    operation = await _ASYNC_OPERATION_SERVICE.get_operation(operation_id)
    
    if operation is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")
    
    # Convert events to response model
    events = [RoomEventModel(type=e.type, payload=e.payload) for e in operation.events]
    
    # Convert deliverable if present
    deliverable_str = None
    if operation.deliverable is not None:
        deliverable_str = operation.deliverable.to_deliverable_string()
    
    return AsyncOperationResponse(
        id=operation.id,
        status=operation.status.value,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
        events=events,
        deliverable=deliverable_str,
        error=operation.error,
    )


@app.post("/council/operations/{operation_id}/cancel")
async def cancel_operation(operation_id: str) -> Dict[str, Any]:
    """Cancel a running async operation."""
    
    success = await _ASYNC_OPERATION_SERVICE.cancel_operation(operation_id)
    
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"Operation {operation_id} not found or already completed"
        )
    
    return {"status": "cancelled", "operation_id": operation_id}

def _build_problem_definition(request: CouncilRequest) -> ProblemDefinition:
    metadata = [Metadata(key=item.key, value=item.value) for item in request.metadata]
    return ProblemDefinition(problem=request.problem, context=request.context, metadata=metadata)


def _validate_room_type(room_type: str) -> None:
    if room_type not in _SUPPORTED_ROOM_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported room type: {room_type}")


def _serialize_room_event(event: RoomEvent) -> Dict[str, Any]:
    return {"type": event.type, "payload": event.payload}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
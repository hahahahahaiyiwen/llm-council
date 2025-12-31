"""Service for managing async operations."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from backend.primitives.deliverable import Deliverable
from backend.rooms.telemetry.room_event import RoomEvent
from backend.services.memory_buffer_subscriber import MemoryBufferSubscriber


class OperationStatus(str, Enum):
    """Status of an async operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AsyncOperation:
    """Represents an async council operation."""
    id: str
    status: OperationStatus
    created_at: datetime
    updated_at: datetime
    events: List[RoomEvent] = field(default_factory=list)
    deliverable: Optional[Deliverable] = None
    error: Optional[str] = None


class AsyncOperationService:
    """Manages async council operations."""

    def __init__(self) -> None:
        self._operations: Dict[str, AsyncOperation] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._subscribers: Dict[str, MemoryBufferSubscriber] = {}
        self._lock = asyncio.Lock()

    async def create_operation(self) -> str:
        """Create a new async operation and return its ID."""
        operation_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        async with self._lock:
            self._operations[operation_id] = AsyncOperation(
                id=operation_id,
                status=OperationStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
            self._subscribers[operation_id] = MemoryBufferSubscriber()
        
        return operation_id

    async def register_task(
        self, operation_id: str, task: asyncio.Task[Deliverable]
    ) -> None:
        """Register a task for an operation and start monitoring it."""
        async with self._lock:
            if operation_id not in self._operations:
                raise ValueError(f"Operation {operation_id} not found")
            
            self._tasks[operation_id] = task
            self._operations[operation_id].status = OperationStatus.RUNNING
            self._operations[operation_id].updated_at = datetime.utcnow()
        
        # Monitor task completion in background
        asyncio.create_task(self._monitor_task(operation_id, task))

    async def _monitor_task(
        self, operation_id: str, task: asyncio.Task[Deliverable]
    ) -> None:
        """Monitor task completion and update operation status."""
        try:
            deliverable = await task
            async with self._lock:
                if operation_id in self._operations:
                    self._operations[operation_id].status = OperationStatus.COMPLETED
                    self._operations[operation_id].deliverable = deliverable
                    self._operations[operation_id].updated_at = datetime.utcnow()
                # Remove task, subscriber from tracking
                self._tasks.pop(operation_id, None)
                self._subscribers.pop(operation_id, None)
        except asyncio.CancelledError:
            async with self._lock:
                if operation_id in self._operations:
                    self._operations[operation_id].status = OperationStatus.CANCELLED
                    self._operations[operation_id].updated_at = datetime.utcnow()
                # Remove task, subscriber from tracking
                self._tasks.pop(operation_id, None)
                self._subscribers.pop(operation_id, None)
        except Exception as exc:
            async with self._lock:
                if operation_id in self._operations:
                    self._operations[operation_id].status = OperationStatus.FAILED
                    self._operations[operation_id].error = str(exc)
                    self._operations[operation_id].updated_at = datetime.utcnow()
                # Remove task, subscriber from tracking
                self._tasks.pop(operation_id, None)
                self._subscribers.pop(operation_id, None)

    async def get_operation(self, operation_id: str) -> Optional[AsyncOperation]:
        """Get operation by ID with latest events."""
        async with self._lock:
            if operation_id not in self._operations:
                return None
            
            operation = self._operations[operation_id]
            
            # Fetch new events from subscriber if available
            if operation_id in self._subscribers:
                subscriber = self._subscribers[operation_id]
                new_events = await subscriber.read_and_flush()
                operation.events.extend(new_events)
            
            return operation

    def get_subscriber(self, operation_id: str) -> Optional[MemoryBufferSubscriber]:
        """Get subscriber for an operation."""
        return self._subscribers.get(operation_id)

    async def cancel_operation(self, operation_id: str) -> bool:
        """Cancel an operation."""
        async with self._lock:
            if operation_id not in self._tasks:
                return False
            
            task = self._tasks[operation_id]
            if not task.done():
                task.cancel()
            
            return True

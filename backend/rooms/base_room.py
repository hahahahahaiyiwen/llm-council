"""Base room implementation with shared functionality."""

from __future__ import annotations

from contextlib import suppress
from typing import List, Optional
from uuid import uuid4, UUID

from backend.members.council_member import CouncilMember
from backend.primitives.problem_definition import ProblemDefinition
from backend.rooms.telemetry.monitor import Monitor
from backend.rooms.room import Room, RoomStatus
from backend.rooms.telemetry.room_event import RoomEvent


class BaseRoom(Room):
    """Base class for room implementations with shared functionality."""

    def __init__(self, problem: ProblemDefinition, name: Optional[str] = None, members: Optional[List[CouncilMember]] = None) -> None:
        self.id: UUID = uuid4()
        self.name: str = name or "Council Room"
        self.status: RoomStatus = RoomStatus.INACTIVE
        self.problem: ProblemDefinition = problem
        self.monitor: Monitor = Monitor()
        self._members: List[CouncilMember] = members or []

    async def __aenter__(self):
        """Async context manager entry - rooms are ready post-construction."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure cleanup."""
        if self._members:
            for member in self._members:
                if hasattr(member, 'dispose'):
                    with suppress(Exception):
                        await member.dispose()
        if self.monitor is not None:
            await self.monitor.dispose()
        return False

    async def _publish_event(self, event_type: str, payload: dict) -> None:
        """Publish an event to the monitor if available."""
        if self.monitor is not None:
            await self.monitor.publish(RoomEvent(type=event_type, payload=payload))

    def _ensure_state_valid(self, from_status: RoomStatus, to_status: RoomStatus) -> None:
        """Ensure the room is in a valid state before operations."""
        if self.status != from_status:
            raise RuntimeError(f"Room must be in {from_status} state to perform this operation")
        if self.problem is None:
            raise RuntimeError("Problem must be set before proceeding")
        if self.monitor is None:
            raise RuntimeError("Monitor must be initialized before proceeding")
        if not self._members or len(self._members) == 0:
            raise RuntimeError("At least one council member must be present before proceeding")
        self.status = to_status
    

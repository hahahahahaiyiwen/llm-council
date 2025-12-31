"""Protocol definitions for Room entities."""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from backend.primitives.deliverable import Deliverable
from backend.primitives.problem_definition import ProblemDefinition
from backend.rooms.telemetry.monitor import Monitor

class RoomStatus(str, Enum):
    """Enumeration of possible room statuses."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    CLOSING = "closing"

class Room(Protocol):
    id: str
    name: str
    problem: ProblemDefinition
    status: RoomStatus
    monitor: Monitor

    async def kickoff(self) -> None:
        """Kick off the room. Active -> InProgress."""
        ...

    async def close(self) -> Deliverable:
        """Close the room and produce a deliverable. InProgress -> Closing -> Inactive."""
        ...

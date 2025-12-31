from __future__ import annotations

import asyncio
from asyncio import Task
from contextlib import suppress

from backend.members.agent_member_factory import AgentMemberFactory
from backend.primitives.deliverable import Deliverable
from backend.primitives.problem_definition import ProblemDefinition
from backend.rooms.round_robin_room import RoundRobinRoom
from backend.rooms.telemetry.monitor import Subscriber
from backend.rooms.original_council_room import OriginalCouncilRoom
from backend.rooms.room import Room


class CouncilService:
    def __init__(self) -> None:
        self._factory = AgentMemberFactory()

    async def run_council_session(
        self,
        problem: ProblemDefinition,
        num_of_members: int,
        timeout: float,
        subscriber: Subscriber,
        room_type: str = "original"
    ) -> Deliverable:
        """Set up a council session and run it."""
        room = await self._prepare_room(problem, num_of_members, room_type)
        await room.monitor.subscribe(subscriber)
        return await self._run_session(room, timeout)

    async def _prepare_room(
        self,
        problem: ProblemDefinition,
        count: int,
        room_type: str,
    ) -> Room:
        members = self._factory.create_multiple_agent_members(count=count)

        if room_type == "original":
            room = OriginalCouncilRoom(problem=problem, members=members)
        elif room_type == "round_robin":
            room = RoundRobinRoom(problem=problem, members=members)
        else:
            raise ValueError(f"Unsupported room type: {room_type}")

        return room

    async def _run_session(self, room: Room, timeout: float) -> Deliverable:
        # Use async context manager to ensure cleanup happens
        async with room:
            kickoff_task = asyncio.create_task(room.kickoff())

            try:
                await asyncio.wait_for(kickoff_task, timeout=timeout)
                return await room.close()
            except asyncio.TimeoutError:
                kickoff_task.cancel()
                with suppress(asyncio.CancelledError):
                    await kickoff_task
                await asyncio.sleep(5) # Grace period. Remote agent tasks may still be running.
                return await room.close()
            except Exception:
                kickoff_task.cancel()
                with suppress(asyncio.CancelledError):
                    await kickoff_task
                raise

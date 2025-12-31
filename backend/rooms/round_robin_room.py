"""Round-robin room implementation for sequential discussions."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from backend.members.council_member import BinaryResponse, CouncilMember
from backend.members.tools.vote import get_vote_result, prepare_vote_tool
from backend.primitives.deliverable import Deliverable
from backend.primitives.problem_definition import ProblemDefinition
from backend.primitives.problem_metadata import Metadata
from backend.rooms.facilities.whiteboard import Whiteboard
from backend.rooms.base_room import BaseRoom
from backend.rooms.room import RoomStatus

_SESSIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "sessions"


class RoundRobinRoom(BaseRoom):
	"""Room that conducts a round-robin style discussion.

	Each member contributes sequentially during kickoff. When the room closes,
	all members provide a concluding statement, also in turn order."""

	def __init__(self, problem: ProblemDefinition, members: List[CouncilMember], name: str = None, moderator: CouncilMember = None) -> None:
		super().__init__(problem, name=name or "Round Robin Room", members=members)
		self._whiteboard = Whiteboard()
		self._moderator = moderator or random.choice(self._members)

	async def __aexit__(self, exc_type, exc_val, exc_tb):
		if self._whiteboard is not None:
			self._persist_session_transcript(await self._whiteboard.read())
		await super().__aexit__(exc_type, exc_val, exc_tb)

	async def _write_to_whiteboard(self, event_type: str, identifier: str, content: str, reasoning: str = "") -> None:
		now = datetime.now(timezone.utc)
		
		await self._whiteboard.append(
			identifier=identifier,
			content=content,
			timestamp=now
		)

		await self._publish_event(
			f"round_robin.{event_type}",
			{
				"member": identifier,
				"timestamp": now.isoformat(),
				"message": content,
				"reasoning": reasoning,
			},
		)

	async def kickoff(self) -> None:
		self._ensure_state_valid(RoomStatus.INACTIVE, RoomStatus.ACTIVE)

		await self._whiteboard.set_problem(self.problem)

		await self._publish_event(
			"problem_statement",
			{"problem": self.problem.to_problem_string().strip()},
		)

		# System
		opening_message = f"The round-robin discussion has started. Members will contribute in turn. Moderator {self._moderator.name} will decide if the discussion should continue or end."

		await self._write_to_whiteboard(
			"opening_announcement",
			"system",
			opening_message
		)

		# Round-robin discussion
		while True:
			for member in self._members:
				if member == self._moderator:
					response = await self._moderator.think(
						await self._whiteboard.read(since=self._moderator.last_response_time) +
						"Based on the current discussion, do you think we have enough information to conclude the round-robin session?",
						BinaryResponse
					)

					if response is not None:
						await self._write_to_whiteboard(
							"moderator_decision",
							self._moderator.name,
							"I think we should conclude the discussion now." if response.response else "I think we should continue the discussion.",
							response.reasoning)
						if response.response:
							# Moderator decided to end the discussion
							return
				else:
					response = await member.think_and_respond(await self._whiteboard.read(since=member.last_response_time))

					if response:
						await self._write_to_whiteboard("member_response", member.name, response.response, response.reasoning)

	async def close(self) -> Deliverable:
		self._ensure_state_valid(RoomStatus.ACTIVE, RoomStatus.CLOSING)

		# System
		closing_message = f"The round-robin discussion has ended. {self._moderator.name} please provide concluding statements and produce a deliverable that answers the problem."

		await self._write_to_whiteboard("closing_announcement", "system", closing_message)

		# Conclusion
		response = await self._moderator.think_and_respond(await self._whiteboard.read(since=self._moderator.last_response_time))

		conclusion = {
			"member": self._moderator.name,
			"response": response.response,
			"reasoning": response.reasoning,
		}

		await self._write_to_whiteboard(
			"conclusion",
			self._moderator.name,
			response.response,
			response.reasoning)

		# Vote confidence score
		prepare_vote_tool()

		closing_message = f"""Now every member will vote a confidence score for the conclusion using vote tool."""

		await self._write_to_whiteboard("closing_announcement", "system", closing_message)

		for member in self._members:
			response = await member.think_and_respond(
				await self._whiteboard.read(since=member.last_response_time) +
				"Please using vote tool to vote a confidence score between 0.0 and 1.0 for the conclusion provided by the moderator."
			)

			if response:
				await self._write_to_whiteboard("member_response", member.name, response.response, response.reasoning)

		deliverable = self._build_deliverable(conclusion, get_vote_result())
		
		return deliverable

	def _build_deliverable(
		self,
		conclusion: dict[str, Optional[str]],
		score: Optional[float] = None,
	) -> Deliverable:
		lines = []
		lines.append("## Round Robin Conclusion")
		lines.append("")
		lines.append(f"### Conclusion by {conclusion['member']}")
		lines.append(conclusion['response'] or "")
		lines.append("")
		if score:
			lines.append(f"**Confidence Score:** {score:.2f}")
			lines.append("")

		return Deliverable(
			problem=self.problem,
			content="\n".join(lines),
			metadata=[
				Metadata(key="room_type", value="round_robin"),
				Metadata(key="member_count", value=str(len(self._members)))
			]
		)
	
	def _ensure_state_valid(self, from_status: RoomStatus, to_status: RoomStatus) -> None:
		if self._whiteboard is None:
			raise RuntimeError("Whiteboard must be initialized before kickoff")
		super()._ensure_state_valid(from_status, to_status)

	def _persist_session_transcript(self, transcript: str) -> None:
		_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
		timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
		filename = f"{self.id}-{timestamp}.md"
		path = _SESSIONS_DIR / filename
		path.write_text(transcript, encoding="utf-8")

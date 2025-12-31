from __future__ import annotations

import asyncio
from collections import deque
from typing import Deque, List, Optional

from backend.rooms.telemetry.room_event import RoomEvent
from backend.rooms.telemetry.monitor import Subscriber


class MemoryBufferSubscriber(Subscriber):
	"""In-memory subscriber that buffers room events until read."""

	def __init__(self, max_events: Optional[int] = None) -> None:
		self._buffer: Deque[RoomEvent] = deque(maxlen=max_events)
		self._lock = asyncio.Lock()
		self._completed = False
		self._error: Optional[Exception] = None

	async def on_room_event(self, event: RoomEvent) -> None:
		async with self._lock:
			self._buffer.append(event)

	async def on_completed(self) -> None:
		async with self._lock:
			self._completed = True

	async def on_error(self, exc: Exception) -> None:
		async with self._lock:
			self._error = exc

	async def read_and_flush(self) -> List[RoomEvent]:
		async with self._lock:
			events = list(self._buffer)
			self._buffer.clear()
			return events

	async def snapshot(self) -> dict:
		async with self._lock:
			return {
				"events": list(self._buffer),
				"completed": self._completed,
				"error": self._error,
			}

"""Monitor implementation that broadcasts room events to subscribers."""

from __future__ import annotations

import asyncio
import uuid
from backend.rooms.telemetry.room_event import RoomEvent
from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict, List
		

class Monitor:
	"""Asyncio-based event distributor for room events."""

	def __init__(self, capacity: int = 100) -> None:
		self.id: str = str(uuid.uuid4())
		self._queue: asyncio.Queue[RoomEvent] = asyncio.Queue(maxsize=capacity)
		self._subscribers: Dict[Subscriber, asyncio.Event] = {}
		self._shutdown = asyncio.Event()
		self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
		self._disposed = False

	async def dispose(self):
		if self._disposed:
			return False

		self._disposed = True
		self._shutdown.set()
		self._dispatcher_task.cancel()

		with suppress(asyncio.CancelledError):
			await self._dispatcher_task

		tasks: List[Awaitable[Any]] = []
		for subscriber, cancellation in list(self._subscribers.items()):
			cancellation.set()
			tasks.append(subscriber.on_completed())
		self._subscribers.clear()

		for task in tasks:
			with suppress(Exception):
				await task

		return False

	def _ensure_not_disposed(self) -> None:
		if self._disposed:
			raise RuntimeError("Monitor has been disposed")

	async def publish(self, event: RoomEvent) -> None:
		self._ensure_not_disposed()
		await self._queue.put(event)

	async def subscribe(self, subscriber: Subscriber) -> AsyncSubscription:
		self._ensure_not_disposed()

		if subscriber in self._subscribers:
			raise ValueError("Subscriber already registered")

		cancellation = asyncio.Event()
		self._subscribers[subscriber] = cancellation

		async def dispose() -> None:
			if subscriber in self._subscribers:
				self._subscribers.pop(subscriber).set()
				with suppress(Exception):
					await subscriber.on_completed()

		return AsyncSubscription(dispose)

	async def _dispatch_loop(self) -> None:
		try:
			while not self._shutdown.is_set():
				try:
					event = await asyncio.wait_for(
						self._queue.get(),
						timeout=0.2,
					)
				except asyncio.TimeoutError:
					continue

				await self._broadcast(event)
				self._queue.task_done()

			await self._notify_completion()
		except asyncio.CancelledError:
			await self._notify_completion()
		except Exception as exc:  # pragma: no cover - defensive
			await self._notify_error(exc)

	async def _broadcast(self, event: RoomEvent) -> None:
		coros: List[Awaitable[Any]] = []

		for subscriber, cancellation in list(self._subscribers.items()):
			if cancellation.is_set():
				continue

			coros.append(self._dispatch_to_subscriber(subscriber, event, cancellation))

		if not coros:
			return

		for coro in asyncio.as_completed(coros):
			with suppress(Exception):
				await coro

	async def _dispatch_to_subscriber(
		self,
		subscriber: Subscriber,
		event: RoomEvent,
		cancellation: asyncio.Event,
	) -> None:
		if cancellation.is_set():
			return
		try:
			await subscriber.on_room_event(event)
		except asyncio.CancelledError:
			cancellation.set()
		except Exception as exc:
			cancellation.set()

	async def _notify_completion(self) -> None:
		for subscriber, cancellation in list(self._subscribers.items()):
			if cancellation.is_set():
				continue
			with suppress(Exception):
				await subscriber.on_completed()

	async def _notify_error(self, exc: Exception) -> None:
		for subscriber, cancellation in list(self._subscribers.items()):
			if cancellation.is_set():
				continue
			with suppress(Exception):
				await subscriber.on_error(exc)

class AsyncSubscription:
	"""Async disposable subscription wrapper."""

	def __init__(self, dispose: Callable[[], Awaitable[None]]) -> None:
		self._dispose = dispose
		self._disposed = False

	async def dispose(self) -> None:
		if self._disposed:
			return
		self._disposed = True
		await self._dispose()

class Subscriber(asyncio.Protocol):
	async def on_room_event(self, event: RoomEvent) -> None:
		...

	async def on_completed(self) -> None:
		...

	async def on_error(self, exc: Exception) -> None:
		...
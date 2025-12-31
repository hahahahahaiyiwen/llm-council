import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional

from backend.primitives.problem_definition import ProblemDefinition


@dataclass(frozen=True)
class _Entry:
    identifier: str
    timestamp: datetime
    content: str

class Whiteboard:
    """Thread safe append-only storage for structured meeting context."""

    def __init__(
        self,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._clock: Callable[[], datetime] = clock or self._utcnow
        self._lock = asyncio.Lock()
        self._entries: List[_Entry] = []
        self._problem: Optional[ProblemDefinition] = None

    async def read(
        self,
        since: Optional[datetime] = None,
    ) -> str:
        """Read note entries as formatted text, optionally filtering by timestamp."""
        async with self._lock:
            if since is None:
                pending_entries: List[_Entry] = list(self._entries)
            else:
                pending_entries = [
                    entry for entry in self._entries if entry.timestamp >= since
                ]
            problem = self._problem

        return self._format_note_entry(pending_entries, since=since, problem=problem)
    
    async def set_problem(self, problem: ProblemDefinition):
        """Set the problem definition for the whiteboard."""
        async with self._lock:
            self._problem = problem

    async def append(
        self,
        identifier: str,
        content: str,
        timestamp: Optional[datetime] = None,
    ):
        """Append a new note entry."""
        if not content:
            raise ValueError("content must be provided")

        entry = _Entry(
            identifier=identifier,
            timestamp=timestamp or self._clock(),
            content=content,
        )

        async with self._lock:
            self._entries.append(entry)

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)
    
    def _format_note_entry(
        self,
        entries: List[_Entry],
        since: Optional[datetime] = None,
        problem: Optional[ProblemDefinition] = None,
    ) -> str:
        """Format entries as chronological markdown."""
        lines: List[str] = []

        if since is None:
            lines.append("# Problem")
            lines.append(
                problem.to_problem_string() if problem is not None else "No problem defined."
            )
            lines.append("")
            lines.append("# Meeting Notes")
        else:
            lines.append("# Meeting Notes (Since " + since.isoformat() + ")")

        if entries:
            for entry in sorted(entries, key=lambda e: e.timestamp):
                lines.append(
                    f"- [{entry.timestamp.isoformat()}] {entry.identifier}: {entry.content}"
                )
        elif since is not None:
            lines.append("- No new notes.")

        return "\n".join(lines)

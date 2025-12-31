
from dataclasses import dataclass
from typing import Any, Dict
import json


@dataclass(frozen=True)
class RoomEvent:
	"""Represents an event that occurred inside a room."""

	type: str
	payload: Dict[str, Any]

	def to_json(self) -> str:
		return json.dumps({"type": self.type, "payload": self.payload})
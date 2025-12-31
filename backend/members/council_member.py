from datetime import datetime
from typing import Optional, Protocol, TypeVar

T = TypeVar('T')

from pydantic import BaseModel

class BinaryResponse(BaseModel):
    """Represents a binary (yes/no) response from a council member."""
    response: bool
    reasoning: str

    def to_json(self) -> str:
        return self.model_dump_json()

class TextResponse(BaseModel):
	"""Represents the response from a council member."""

	response: str
	reasoning: str

	def to_json(self) -> str:
		return self.model_dump_json()

class CouncilMember(Protocol):
    id: str
    name: str
    last_response_time: Optional[datetime]

    async def think_and_respond(self, problem: str) -> TextResponse:
        ...

    async def think(self, context: str, response_type: type[T]) -> T:
        ...
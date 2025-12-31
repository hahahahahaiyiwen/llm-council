"""Problem definition for LLM Council."""

from dataclasses import dataclass, field


@dataclass
class Metadata:
    """Metadata for problem definitions."""
    key: str
    value: str

"""Problem definition for LLM Council."""

from typing import Optional, List
from dataclasses import dataclass, field
from backend.primitives.problem_metadata import Metadata


@dataclass
class ProblemDefinition:
    """Defines a problem to be solved by the LLM council."""
    
    problem: str
    context: Optional[str] = None
    metadata: List[Metadata] = field(default_factory=list)
    
    def to_problem_string(self) -> str:
        """
        Convert the problem definition to a formatted string.
        
        Returns:
            Formatted problem string with optional context.
        """
        lines = []
        
        lines.append("## Problem Definition")
        lines.append("")
        lines.append((self.problem or "").strip())
        lines.append("")
        
        if self.context and self.context.strip():
            lines.append("## Context")
            lines.append("")
            lines.append(self.context.strip())
            lines.append("")
        
        return "\n".join(lines).rstrip()

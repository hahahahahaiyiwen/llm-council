"""Deliverable definition for LLM Council."""

from typing import Optional, List
from dataclasses import dataclass, field
from backend.primitives.problem_definition import ProblemDefinition
from backend.primitives.problem_metadata import Metadata


@dataclass
class Deliverable:
    """Defines a deliverable to be produced by the LLM council."""
    
    problem: Optional[ProblemDefinition]
    content: str
    metadata: List[Metadata] = field(default_factory=list)
    
    def to_deliverable_string(self) -> str:
        """
        Convert the deliverable to a formatted string.
        
        Returns:
            Formatted deliverable string with optional context.
        """
        lines = []
        
        if self.problem is not None:
            lines.append("# Problem")
            lines.append("")
            lines.append(self.problem.to_problem_string().strip())
            lines.append("")
        
        lines.append("# Deliverable")
        lines.append("")
        lines.append(self.content.strip())
        lines.append("")
        
        return "\n".join(lines).rstrip()
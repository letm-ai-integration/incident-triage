"""Base agent interface.

Agents provide capabilities (reasoning / analysis / generation). Graph nodes
adapt an agent's output to the graph state. Agents must not import the graph
builder or mutate graphs during import.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent[TInput, TResult](ABC):
    """Thin contract every capability-providing agent should implement."""

    name: str = "base_agent"

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> TResult:
        """Execute the agent capability and return its structured result."""
        raise NotImplementedError

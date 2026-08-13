from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseTool(ABC):
    """
    Abstract base class for all tools in the incident triage system.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the tool."""
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        """A description of what the tool does."""
        pass

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> Any:
        """
        Executes the tool with the given input data.
        Returns the structured output of the tool.
        """
        pass

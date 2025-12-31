"""Base tool interface for external service clients."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseTool(ABC):
    """Base interface for all external tools."""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the tool connection."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""
        pass


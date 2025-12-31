"""Base RAG interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseRAG(ABC):
    """Base interface for RAG systems."""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the RAG system."""
        pass
    
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant examples for a query."""
        pass
    
    @abstractmethod
    async def enhance_prompt(self, base_prompt: str, query: str) -> str:
        """Enhance a base prompt with retrieved examples."""
        pass


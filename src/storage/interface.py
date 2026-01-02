"""
Storage backend interface.

Defines the abstract interface for artifact storage, enabling pluggable
backends (local filesystem, S3, etc.).
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StorageBackend(ABC):
    """Abstract storage backend interface."""

    @abstractmethod
    async def store_bytes(self, key: str, data: bytes, metadata: dict[str, Any] | None = None) -> str:
        """Store raw bytes and return the storage key.

        Args:
            key: Storage key/path
            data: Raw bytes to store
            metadata: Optional metadata to associate

        Returns:
            The final storage key
        """
        ...

    @abstractmethod
    async def store_text(self, key: str, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store text content and return the storage key."""
        ...

    @abstractmethod
    async def store_model(self, key: str, model: BaseModel, metadata: dict[str, Any] | None = None) -> str:
        """Store a Pydantic model as JSON."""
        ...

    @abstractmethod
    async def load_bytes(self, key: str) -> bytes:
        """Load raw bytes from storage."""
        ...

    @abstractmethod
    async def load_text(self, key: str) -> str:
        """Load text content from storage."""
        ...

    @abstractmethod
    async def load_model(self, key: str, model_type: type[T]) -> T:
        """Load a Pydantic model from storage."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key from storage. Returns True if deleted."""
        ...

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys with the given prefix."""
        ...

    @abstractmethod
    async def get_metadata(self, key: str) -> dict[str, Any]:
        """Get metadata for a key."""
        ...

    @staticmethod
    def compute_hash(data: bytes) -> str:
        """Compute SHA-256 hash of data."""
        return hashlib.sha256(data).hexdigest()

    @abstractmethod
    def get_local_path(self, key: str) -> Path | None:
        """Get local filesystem path if available (for tools that need file paths)."""
        ...

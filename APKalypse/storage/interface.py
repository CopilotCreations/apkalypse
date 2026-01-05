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
        """Store text content and return the storage key.

        Args:
            key: Storage key/path.
            content: Text content to store.
            metadata: Optional metadata to associate.

        Returns:
            The final storage key.
        """
        ...

    @abstractmethod
    async def store_model(self, key: str, model: BaseModel, metadata: dict[str, Any] | None = None) -> str:
        """Store a Pydantic model as JSON.

        Args:
            key: Storage key/path.
            model: Pydantic model instance to store.
            metadata: Optional metadata to associate.

        Returns:
            The final storage key.
        """
        ...

    @abstractmethod
    async def load_bytes(self, key: str) -> bytes:
        """Load raw bytes from storage.

        Args:
            key: Storage key/path to load from.

        Returns:
            The raw bytes stored at the key.
        """
        ...

    @abstractmethod
    async def load_text(self, key: str) -> str:
        """Load text content from storage.

        Args:
            key: Storage key/path to load from.

        Returns:
            The text content stored at the key.
        """
        ...

    @abstractmethod
    async def load_model(self, key: str, model_type: type[T]) -> T:
        """Load a Pydantic model from storage.

        Args:
            key: Storage key/path to load from.
            model_type: The Pydantic model class to deserialize into.

        Returns:
            The deserialized Pydantic model instance.
        """
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in storage.

        Args:
            key: Storage key/path to check.

        Returns:
            True if the key exists, False otherwise.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key from storage.

        Args:
            key: Storage key/path to delete.

        Returns:
            True if the key was deleted, False otherwise.
        """
        ...

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys with the given prefix.

        Args:
            prefix: Optional prefix to filter keys by.

        Returns:
            List of storage keys matching the prefix.
        """
        ...

    @abstractmethod
    async def get_metadata(self, key: str) -> dict[str, Any]:
        """Get metadata for a key.

        Args:
            key: Storage key/path to get metadata for.

        Returns:
            Dictionary of metadata associated with the key.
        """
        ...

    @staticmethod
    def compute_hash(data: bytes) -> str:
        """Compute SHA-256 hash of data.

        Args:
            data: Raw bytes to hash.

        Returns:
            Hexadecimal string representation of the SHA-256 hash.
        """
        return hashlib.sha256(data).hexdigest()

    @abstractmethod
    def get_local_path(self, key: str) -> Path | None:
        """Get local filesystem path if available.

        Some tools require direct filesystem access. This method provides
        the local path for backends that support it.

        Args:
            key: Storage key/path to get the local path for.

        Returns:
            Local filesystem Path if available, None otherwise.
        """
        ...

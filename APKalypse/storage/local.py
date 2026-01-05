"""
Local filesystem storage backend.

Provides a filesystem-based implementation of the storage interface,
suitable for development and single-machine deployments.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

import aiofiles
import aiofiles.os
from pydantic import BaseModel

from .interface import StorageBackend

T = TypeVar("T", bound=BaseModel)


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: Path) -> None:
        """Initialize local storage.

        Args:
            base_path: Base directory for all storage operations
        """
        self.base_path = base_path.resolve()
        self._metadata_suffix = ".meta.json"

    async def _ensure_parent(self, path: Path) -> None:
        """Ensure parent directory exists.

        Args:
            path: The file path whose parent directory should be created.
        """
        parent = path.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

    def _get_full_path(self, key: str) -> Path:
        """Get full filesystem path for a key.

        Normalizes the key to prevent path traversal attacks and ensures
        the resulting path is within the base storage directory.

        Args:
            key: The storage key to convert to a filesystem path.

        Returns:
            The resolved absolute path within the base storage directory.
        """
        # Normalize key to prevent path traversal
        # Remove leading slashes and any parent directory references
        clean_key = key.lstrip("/\\").replace("..", "").replace(":", "")
        # Resolve and verify it's within base_path
        full_path = (self.base_path / clean_key).resolve()
        
        # Security: Ensure resolved path is within base_path
        try:
            full_path.relative_to(self.base_path)
        except ValueError:
            # Path traversal attempt - return path within base
            clean_key = clean_key.replace("/", "_").replace("\\", "_")
            full_path = self.base_path / clean_key
        
        return full_path

    def _get_metadata_path(self, key: str) -> Path:
        """Get metadata file path for a key.

        Args:
            key: The storage key for which to get the metadata path.

        Returns:
            The path to the metadata file associated with the key.
        """
        return self._get_full_path(key + self._metadata_suffix)

    async def _store_metadata(self, key: str, metadata: dict[str, Any]) -> None:
        """Store metadata for a key.

        Adds standard metadata fields (_stored_at, _key) and writes
        the metadata to a JSON file alongside the stored content.

        Args:
            key: The storage key to associate metadata with.
            metadata: Dictionary of metadata to store.
        """
        meta_path = self._get_metadata_path(key)
        await self._ensure_parent(meta_path)
        
        # Add standard metadata
        metadata["_stored_at"] = datetime.utcnow().isoformat()
        metadata["_key"] = key
        
        async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(metadata, indent=2, default=str))

    async def store_bytes(self, key: str, data: bytes, metadata: dict[str, Any] | None = None) -> str:
        """Store raw bytes to filesystem.

        Args:
            key: The storage key under which to store the data.
            data: The raw bytes to store.
            metadata: Optional metadata to associate with the stored data.

        Returns:
            The storage key where the data was stored.
        """
        full_path = self._get_full_path(key)
        await self._ensure_parent(full_path)
        
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(data)
        
        # Store metadata
        meta = metadata or {}
        meta["size_bytes"] = len(data)
        meta["hash"] = self.compute_hash(data)
        await self._store_metadata(key, meta)
        
        return key

    async def store_text(self, key: str, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store text content to filesystem.

        Args:
            key: The storage key under which to store the content.
            content: The text content to store.
            metadata: Optional metadata to associate with the stored content.

        Returns:
            The storage key where the content was stored.
        """
        full_path = self._get_full_path(key)
        await self._ensure_parent(full_path)
        
        async with aiofiles.open(full_path, "w", encoding="utf-8") as f:
            await f.write(content)
        
        # Store metadata
        meta = metadata or {}
        meta["size_chars"] = len(content)
        meta["hash"] = self.compute_hash(content.encode("utf-8"))
        await self._store_metadata(key, meta)
        
        return key

    async def store_model(self, key: str, model: BaseModel, metadata: dict[str, Any] | None = None) -> str:
        """Store Pydantic model as JSON.

        Args:
            key: The storage key under which to store the model.
            model: The Pydantic model instance to serialize and store.
            metadata: Optional metadata to associate with the stored model.

        Returns:
            The storage key where the model was stored.
        """
        json_content = model.model_dump_json(indent=2)
        
        meta = metadata or {}
        meta["model_type"] = type(model).__name__
        
        return await self.store_text(key, json_content, meta)

    async def load_bytes(self, key: str) -> bytes:
        """Load raw bytes from filesystem.

        Args:
            key: The storage key to load data from.

        Returns:
            The raw bytes stored at the given key.

        Raises:
            FileNotFoundError: If the key does not exist.
        """
        full_path = self._get_full_path(key)
        
        if not full_path.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def load_text(self, key: str) -> str:
        """Load text content from filesystem.

        Args:
            key: The storage key to load content from.

        Returns:
            The text content stored at the given key.

        Raises:
            FileNotFoundError: If the key does not exist.
        """
        full_path = self._get_full_path(key)
        
        if not full_path.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        
        async with aiofiles.open(full_path, "r", encoding="utf-8") as f:
            return await f.read()

    async def load_model(self, key: str, model_type: type[T]) -> T:
        """Load Pydantic model from JSON file.

        Args:
            key: The storage key to load the model from.
            model_type: The Pydantic model class to deserialize into.

        Returns:
            An instance of the specified model type populated with stored data.

        Raises:
            FileNotFoundError: If the key does not exist.
        """
        json_content = await self.load_text(key)
        return model_type.model_validate_json(json_content)

    async def exists(self, key: str) -> bool:
        """Check if key exists in filesystem.

        Args:
            key: The storage key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        return self._get_full_path(key).exists()

    async def delete(self, key: str) -> bool:
        """Delete file from filesystem.

        Removes both the data file and its associated metadata file.

        Args:
            key: The storage key to delete.

        Returns:
            True if the file was deleted, False if it did not exist.
        """
        full_path = self._get_full_path(key)
        meta_path = self._get_metadata_path(key)
        
        deleted = False
        
        if full_path.exists():
            await aiofiles.os.remove(full_path)
            deleted = True
        
        if meta_path.exists():
            await aiofiles.os.remove(meta_path)
        
        return deleted

    async def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys with prefix.

        Args:
            prefix: Optional prefix to filter keys. If empty, lists all keys.

        Returns:
            A sorted list of storage keys matching the prefix.
        """
        search_path = self._get_full_path(prefix) if prefix else self.base_path
        
        if not search_path.exists():
            return []
        
        keys = []
        base_len = len(str(self.base_path)) + 1
        
        for path in search_path.rglob("*"):
            if path.is_file() and not path.name.endswith(self._metadata_suffix):
                # Convert to key format
                key = str(path)[base_len:].replace("\\", "/")
                keys.append(key)
        
        return sorted(keys)

    async def get_metadata(self, key: str) -> dict[str, Any]:
        """Get metadata for a key.

        Args:
            key: The storage key to retrieve metadata for.

        Returns:
            A dictionary of metadata, or an empty dict if no metadata exists.
        """
        meta_path = self._get_metadata_path(key)
        
        if not meta_path.exists():
            return {}
        
        async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)

    def get_local_path(self, key: str) -> Path | None:
        """Get local filesystem path for a key.

        Args:
            key: The storage key to get the path for.

        Returns:
            The filesystem path if the key exists, None otherwise.
        """
        full_path = self._get_full_path(key)
        if full_path.exists():
            return full_path
        return None

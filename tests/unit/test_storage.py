"""Unit tests for storage backend."""

import pytest
from pathlib import Path

from src.storage import LocalStorageBackend
from src.models.behavior import ScreenModel


@pytest.mark.asyncio
class TestLocalStorageBackend:
    """Tests for local filesystem storage."""

    async def test_store_and_load_bytes(self, temp_dir):
        """Test storing and loading bytes."""
        storage = LocalStorageBackend(temp_dir)
        
        data = b"Hello, World!"
        key = "test/data.bin"
        
        stored_key = await storage.store_bytes(key, data)
        assert stored_key == key
        
        loaded = await storage.load_bytes(key)
        assert loaded == data

    async def test_store_and_load_text(self, temp_dir):
        """Test storing and loading text."""
        storage = LocalStorageBackend(temp_dir)
        
        content = "Hello, World!"
        key = "test/text.txt"
        
        await storage.store_text(key, content)
        loaded = await storage.load_text(key)
        assert loaded == content

    async def test_store_and_load_model(self, temp_dir):
        """Test storing and loading Pydantic models."""
        storage = LocalStorageBackend(temp_dir)
        
        model = ScreenModel(
            screen_id="s1",
            screen_name="Test Screen",
            description="A test screen",
        )
        key = "test/screen.json"
        
        await storage.store_model(key, model)
        loaded = await storage.load_model(key, ScreenModel)
        
        assert loaded.screen_id == model.screen_id
        assert loaded.screen_name == model.screen_name

    async def test_exists(self, temp_dir):
        """Test checking if key exists."""
        storage = LocalStorageBackend(temp_dir)
        
        key = "test/exists.txt"
        assert not await storage.exists(key)
        
        await storage.store_text(key, "content")
        assert await storage.exists(key)

    async def test_delete(self, temp_dir):
        """Test deleting a key."""
        storage = LocalStorageBackend(temp_dir)
        
        key = "test/delete.txt"
        await storage.store_text(key, "content")
        assert await storage.exists(key)
        
        deleted = await storage.delete(key)
        assert deleted
        assert not await storage.exists(key)
        
        # Deleting non-existent key returns False
        deleted = await storage.delete(key)
        assert not deleted

    async def test_list_keys(self, temp_dir):
        """Test listing keys."""
        storage = LocalStorageBackend(temp_dir)
        
        await storage.store_text("dir1/file1.txt", "content1")
        await storage.store_text("dir1/file2.txt", "content2")
        await storage.store_text("dir2/file3.txt", "content3")
        
        all_keys = await storage.list_keys()
        assert len(all_keys) == 3
        
        dir1_keys = await storage.list_keys("dir1")
        assert len(dir1_keys) == 2

    async def test_get_metadata(self, temp_dir):
        """Test getting metadata."""
        storage = LocalStorageBackend(temp_dir)
        
        key = "test/meta.txt"
        await storage.store_text(key, "content", {"custom": "value"})
        
        meta = await storage.get_metadata(key)
        assert "custom" in meta
        assert meta["custom"] == "value"
        assert "hash" in meta
        assert "_stored_at" in meta

    async def test_get_local_path(self, temp_dir):
        """Test getting local path."""
        storage = LocalStorageBackend(temp_dir)
        
        key = "test/path.txt"
        await storage.store_text(key, "content")
        
        path = storage.get_local_path(key)
        assert path is not None
        assert path.exists()
        
        # Non-existent key returns None
        assert storage.get_local_path("nonexistent") is None

    async def test_compute_hash(self, temp_dir):
        """Test hash computation."""
        storage = LocalStorageBackend(temp_dir)
        
        data = b"test data"
        hash1 = storage.compute_hash(data)
        hash2 = storage.compute_hash(data)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    async def test_path_traversal_prevention(self, temp_dir):
        """Test that path traversal is prevented."""
        storage = LocalStorageBackend(temp_dir)
        
        # Attempt path traversal
        key = "../../../etc/passwd"
        await storage.store_text(key, "content")
        
        # Should be stored within base path
        path = storage.get_local_path(key)
        if path:
            assert str(temp_dir) in str(path)

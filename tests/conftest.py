"""Test configuration for APKalypse."""

import pytest
import asyncio
from pathlib import Path
import tempfile

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_apk_bytes():
    """Create minimal valid APK-like bytes for testing."""
    import zipfile
    import io
    
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        # Add minimal required files
        zf.writestr('AndroidManifest.xml', b'<?xml version="1.0"?><manifest/>')
        zf.writestr('classes.dex', b'dex\n035\x00')
    
    return buffer.getvalue()

@pytest.fixture
def sample_apk(temp_dir, sample_apk_bytes):
    """Create a sample APK file for testing."""
    apk_path = temp_dir / "sample.apk"
    apk_path.write_bytes(sample_apk_bytes)
    return apk_path

@pytest.fixture
def storage(temp_dir):
    """Create a storage backend for testing."""
    from src.storage import LocalStorageBackend
    return LocalStorageBackend(temp_dir)

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

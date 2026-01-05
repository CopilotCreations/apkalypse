"""Test configuration for APKalypse."""

import pytest
import asyncio
from pathlib import Path
import tempfile

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests.

    Yields:
        Path: A Path object pointing to the temporary directory.
            The directory is automatically cleaned up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_apk_bytes():
    """Create minimal valid APK-like bytes for testing.

    Creates a minimal ZIP archive containing the basic structure of an APK file,
    including an AndroidManifest.xml and a classes.dex file.

    Returns:
        bytes: The raw bytes of a minimal valid APK-like ZIP archive.
    """
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
    """Create a sample APK file for testing.

    Args:
        temp_dir: Pytest fixture providing a temporary directory path.
        sample_apk_bytes: Pytest fixture providing minimal APK bytes.

    Returns:
        Path: The path to the created sample APK file.
    """
    apk_path = temp_dir / "sample.apk"
    apk_path.write_bytes(sample_apk_bytes)
    return apk_path

@pytest.fixture
def storage(temp_dir):
    """Create a storage backend for testing.

    Args:
        temp_dir: Pytest fixture providing a temporary directory path.

    Returns:
        LocalStorageBackend: A local storage backend instance configured
            to use the temporary directory.
    """
    from src.storage import LocalStorageBackend
    return LocalStorageBackend(temp_dir)

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests.

    Creates a new event loop for the test session. This fixture is scoped
    to the session level, meaning the same loop is reused for all async tests.

    Yields:
        asyncio.AbstractEventLoop: The event loop instance for running
            async tests. The loop is closed after the session ends.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

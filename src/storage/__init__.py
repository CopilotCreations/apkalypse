"""Storage abstraction for Behavior2Build."""

from .interface import StorageBackend
from .local import LocalStorageBackend

__all__ = ["StorageBackend", "LocalStorageBackend"]

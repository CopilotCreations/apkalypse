"""Storage abstraction for APKalypse."""

from .interface import StorageBackend
from .local import LocalStorageBackend

__all__ = ["StorageBackend", "LocalStorageBackend"]

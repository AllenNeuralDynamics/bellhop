from importlib.metadata import version

from . import shims
from .data_transfer import configure, delete_data, transfer_data

__version__ = version(__package__)

__all__ = ["configure", "delete_data", "shims", "transfer_data"]

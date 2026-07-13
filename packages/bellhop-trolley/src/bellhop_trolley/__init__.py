from importlib.metadata import version

from .data_transfer import transfer_data, delete_data

__version__ = version(__package__)

__all__ = ["transfer_data", "delete_data"]

from functools import cache
from typing import Callable

from pydantic import validate_call
from upath import UPath
from upath.implementations.cloud import GCSPath, S3Path
from upath.implementations.local import LocalPath

from bellhop_trolley import shims


class configure:
    """
    Apply shim settings permanently or temporarily as a context manager.

    Permanent (module-level setup):
    >>> bellhop_trolley.configure(local=shims.local.LocalTransferSettings(copy_method="robocopy"))

    >>> # Temporary override:
    >>> with bellhop_trolley.configure(local=shims.local.LocalTransferSettings(copy_method="robocopy")):
    ...     transfer_data(src, dst)
        # previous settings restored here
    """

    def __init__(
        self,
        local: shims.local.LocalTransferSettings | None = None,
        s3: shims.s3.S3TransferSettings | None = None,
        gcs: shims.google.GoogleCloudTransferSettings | None = None,
    ):
        self._tokens = []
        for context, settings in [
            (shims.local.context, local),
            (shims.s3.context, s3),
            (shims.google.context, gcs),
        ]:
            if settings is not None:
                self._tokens.append((context, context.set(settings)))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        for context, token in reversed(self._tokens):
            context.reset(token)
        self._tokens.clear()


## Data transfer backends and selection logic

CopyFunc = Callable[[UPath, UPath], None]

_copy_backends: dict[tuple[type, type], CopyFunc] = {
    (LocalPath, LocalPath): shims.local.copy,
    (LocalPath, S3Path): shims.s3.upload,
    (S3Path, LocalPath): shims.s3.download,
    # (LocalPath, GCSPath): shims.google.copy,
    # (Path, GCSPath): GenericObjectStorageUploader,
}

_delete_backends: dict[type, Callable[[UPath], None]] = {
    LocalPath: shims.local.delete,
    S3Path: shims.s3.delete,
    GCSPath: shims.google.delete,
}

# Helpers for selecting from these dicts, so we can use `isinstance` instead of
# exact type matches when determining which backend to use.


@cache
@validate_call(config={"arbitrary_types_allowed": True})
def _get_copier(source: UPath, destination: UPath) -> CopyFunc:
    """
    Get the appropriate backend for transferring data based on source and destination types.
    """
    for (src_type, dest_type), backend in _copy_backends.items():
        if isinstance(source, src_type) and isinstance(destination, dest_type):
            return backend
    raise ValueError(f"No uploader found for {type(source)} to {type(destination)}")


@cache
@validate_call(config={"arbitrary_types_allowed": True})
def _get_deleter(path: UPath) -> Callable[[UPath], None]:
    for cls, fn in _delete_backends.items():
        if isinstance(path, cls):
            return fn
    raise ValueError(f"No delete backend found for {type(path)}")


### Public interface


@validate_call(config={"arbitrary_types_allowed": True})
def transfer_data(source: UPath, destination: UPath) -> None:
    """
    Upload a file from source to destination.
    """
    copier = _get_copier(source, destination)
    copier(source, destination)


@validate_call(config={"arbitrary_types_allowed": True})
def delete_data(path: UPath) -> None:
    """
    Delete a file or directory at the specified path.
    """
    backend = _get_deleter(path)
    backend(path)

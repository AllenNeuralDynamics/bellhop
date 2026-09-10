from pathlib import Path
from typing import Optional

from google.cloud.storage import Client, transfer_manager
from pydantic_settings import BaseSettings
from upath.implementations.cloud import GCSPath

from bellhop_trolley._config_utils import ContextConfig


class GoogleCloudTransferSettings(BaseSettings):
    gcs_credential_json: Optional[Path] = None
    upload_workers: int = 8


context = ContextConfig(GoogleCloudTransferSettings)


def upload(source: Path, destination: GCSPath):
    if source.is_dir():
        _upload_directory(source, destination)
    else:
        _upload_file(source, destination)


def download(source: GCSPath, destination: Path):
    if source.is_dir():
        _download_directory(source, destination)
    else:
        _download_file(source, destination)


def delete(path: GCSPath):
    """
    Delete a file or directory at the specified path.
    """
    client = _gcs_client(credential_json=path.storage_options.get("token"))
    bucket = client.bucket(path.drive)
    blob = bucket.blob("/".join(path.parts[2:]))
    blob.delete()


def _gcs_client(credential_json: Optional[Path] = None) -> Client:
    """
    Returns a Google Cloud Storage client using the service account credentials.

    :return: storage.Client - authenticated GCS client
    """
    if credential_json is not None:
        return Client.from_service_account_json(credential_json)

    config = GoogleCloudTransferSettings.current()
    if config.gcs_credential_json is None:
        raise ValueError("GCS credential JSON path is not set in the configuration.")

    return Client.from_service_account_json(config.gcs_credential_json)


def _upload_file(source: Path, destination: GCSPath):
    client = _gcs_client(credential_json=destination.storage_options.get("token"))

    # Get the bucket
    bucket = client.bucket(destination.drive)

    # construct the blob name without protocol and bucket name
    destination_key = "/".join(destination.parts[2:])

    # Create a blob and upload the file
    blob = bucket.blob(destination_key)
    blob.upload_from_filename(source)


def _upload_directory(source: Path, destination: GCSPath):
    client = _gcs_client(credential_json=destination.storage_options.get("token"))
    bucket = client.bucket(destination.drive)

    # Generate a list of paths (in string form) relative to the `directory`.
    paths = source.rglob("*")

    # Filter so the list only includes files, not directories themselves.
    file_paths = [path for path in paths if path.is_file()]

    # These paths are relative to the current working directory. Next, make them
    # relative to `directory`
    relative_paths = [path.relative_to(source) for path in file_paths]

    # Finally, convert them all to strings.
    string_paths = [str(path) for path in relative_paths]

    # Start the upload.
    results: list[None | Exception] = transfer_manager.upload_many_from_filenames(
        bucket,
        string_paths,
        source_directory=source,
        max_workers=GoogleCloudTransferSettings.current().upload_workers,
    )

    failures = {name: result for name, result in zip(string_paths, results) if isinstance(result, Exception)}

    if len(failures) > 0:
        raise Exception()

    return failures


def _download_file(source: GCSPath, destination: Path):
    client = _gcs_client(credential_json=source.storage_options.get("token"))
    bucket = client.bucket(source.drive)
    blob = bucket.blob("/".join(source.parts[2:]))
    # blob.download_to_filename(destination)

    # TODO: implement canonical download method from google
    raise NotImplementedError()


def _download_directory(source: GCSPath, destination: Path):
    client = _gcs_client(credential_json=source.storage_options.get("token"))
    bucket = client.bucket(source.drive)

    # prefix = "/".join(source.parts[2:])
    # blobs = list(bucket.list_blobs(prefix=prefix))

    # for blob in blobs:
    #     relative_path = Path(blob.name).relative_to(prefix)
    #     local_path = destination / relative_path
    #     local_path.parent.mkdir(parents=True, exist_ok=True)
    #     blob.download_to_filename(local_path)

    # TODO: implement canonical download method from google for directories
    raise NotImplementedError()

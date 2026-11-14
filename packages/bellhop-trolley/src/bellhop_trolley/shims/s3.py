from pathlib import Path

import boto3
from pydantic_settings import BaseSettings
from upath.implementations.cloud import S3Path

from bellhop_trolley._config_utils import ContextConfig

# TODO: Add helpers for credentials


class S3TransferSettings(BaseSettings): ...


context = ContextConfig(S3TransferSettings)


def upload(source: Path, destination: S3Path):
    if source.is_dir():
        _upload_directory(source, destination)
    else:
        _upload_file(source, destination)


def download(source: S3Path, destination: Path):
    if source.is_dir():
        _download_directory(source, destination)
    else:
        _download_file(source, destination)


def delete(path: S3Path):
    """Delete a file or directory at the specified S3 path."""
    s3 = boto3.client("s3")
    bucket = path.drive
    key = "/".join(path.parts[1:])

    # Check if it's a directory by listing objects with the same prefix
    # MaxKeys=1 optimizes performance and minimizes data transfer costs
    response = s3.list_objects_v2(Bucket=bucket, Prefix=key + "/", MaxKeys=1)

    # If 'Contents' exists in the response, items are nested under this prefix
    is_dir = "Contents" in response

    if is_dir:
        # List all objects under the directory and delete them
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=key):
            if "Contents" in page:
                delete_us = {"Objects": [{"Key": obj["Key"]} for obj in page["Contents"]]}

                # Batch delete up to 1,000 objects at once
                s3.delete_objects(Bucket=bucket, Delete=delete_us)
    else:
        s3.delete_object(Bucket=bucket, Key=key)


def _upload_file(source: Path, destination: S3Path):
    """Upload a local file to an s3 bucket"""
    s3 = boto3.client("s3")
    bucket = destination.drive
    key = "/".join(destination.parts[1:])
    s3.upload_file(str(source), bucket, key)


def _upload_directory(source: Path, destination: S3Path):
    """Upload a local directory to an s3 bucket"""
    for local_file in source.rglob("*"):
        if local_file.is_file():
            relative = local_file.relative_to(source)
            dest_file = destination / relative.as_posix()
            _upload_file(local_file, dest_file)


def _download_file(source: S3Path, destination: Path):
    """Download a file from an s3 bucket to local storage"""
    s3 = boto3.client("s3")
    bucket = source.drive
    key = "/".join(source.parts[1:])
    destination.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(bucket, key, str(destination))


def _download_directory(source: S3Path, destination: Path):
    """Download a directory from an s3 bucket to local storage"""
    s3 = boto3.client("s3")
    bucket = source.drive
    prefix = "/".join(source.parts[1:])
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            relative = key[len(prefix) :]
            local_file = destination / relative
            local_file.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(local_file))

"""
Contract tests for the S3 shim.

Uses moto to mock AWS — no real credentials or network access required.
Tests mirror the same behaviors as test_local.py where applicable.
"""

from upath import UPath

from bellhop_trolley.shims.s3 import _download_directory, _download_file, _upload_directory, _upload_file, delete

MOCK_BUCKET = "mock-bucket"


def _list_keys(s3_client):
    keys = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=MOCK_BUCKET):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys


# ── upload: file ─────────────────────────────────────────────────────────────


def test_upload_file_creates_s3_object(s3_client, source_file):
    dst = UPath(f"s3://{MOCK_BUCKET}/file.txt")
    _upload_file(source_file, dst)
    obj = s3_client.get_object(Bucket=MOCK_BUCKET, Key="file.txt")
    assert obj["Body"].read().decode() == "hello"


# ── upload: directory ────────────────────────────────────────────────────────


def test_upload_directory_creates_all_objects(s3_client, source_dir):
    dst = UPath(f"s3://{MOCK_BUCKET}/data")
    _upload_directory(source_dir, dst)
    keys = _list_keys(s3_client)
    assert "data/a.txt" in keys
    assert "data/subdir/b.txt" in keys


def test_upload_directory_preserves_nested_structure(s3_client, source_dir):
    dst = UPath(f"s3://{MOCK_BUCKET}/data")
    _upload_directory(source_dir, dst)
    obj = s3_client.get_object(Bucket=MOCK_BUCKET, Key="data/subdir/b.txt")
    assert obj["Body"].read().decode() == "b"


# ── download: file ───────────────────────────────────────────────────────────


def test_download_file_content(s3_client, tmp_path):
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="file.txt", Body=b"hello")
    dst = tmp_path / "file.txt"
    _download_file(UPath(f"s3://{MOCK_BUCKET}/file.txt"), dst)
    assert dst.read_text() == "hello"


def test_download_file_creates_parent_dirs(s3_client, tmp_path):
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="file.txt", Body=b"hello")
    dst = tmp_path / "deep" / "nested" / "file.txt"
    _download_file(UPath(f"s3://{MOCK_BUCKET}/file.txt"), dst)
    assert dst.read_text() == "hello"


# ── download: directory ──────────────────────────────────────────────────────


def test_download_directory_recursively(s3_client, tmp_path):
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="data/a.txt", Body=b"a")
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="data/subdir/b.txt", Body=b"b")
    dst = tmp_path / "dst"
    _download_directory(UPath(f"s3://{MOCK_BUCKET}/data"), dst)
    assert (dst / "a.txt").read_text() == "a"
    assert (dst / "subdir" / "b.txt").read_text() == "b"


def test_download_directory_creates_parent_dirs(s3_client, tmp_path):
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="data/a.txt", Body=b"a")
    dst = tmp_path / "deep" / "nested" / "dst"
    _download_directory(UPath(f"s3://{MOCK_BUCKET}/data"), dst)
    assert (dst / "a.txt").exists()


# ── delete ───────────────────────────────────────────────────────────────────


def test_delete_file(s3_client):
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="file.txt", Body=b"data")
    delete(UPath(f"s3://{MOCK_BUCKET}/file.txt"))
    assert _list_keys(s3_client) == []


def test_delete_directory_removes_all_objects(s3_client):
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="data/a.txt", Body=b"a")
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="data/subdir/b.txt", Body=b"b")
    delete(UPath(f"s3://{MOCK_BUCKET}/data"))
    assert _list_keys(s3_client) == []


def test_delete_does_not_affect_other_keys(s3_client):
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="data/a.txt", Body=b"a")
    s3_client.put_object(Bucket=MOCK_BUCKET, Key="other/b.txt", Body=b"b")
    delete(UPath(f"s3://{MOCK_BUCKET}/data"))
    assert _list_keys(s3_client) == ["other/b.txt"]

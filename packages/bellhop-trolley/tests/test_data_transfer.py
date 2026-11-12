"""
Unit tests for bellhop_trolley.data_transfer.
"""

import pytest
from upath import UPath

from bellhop_trolley import shims
from bellhop_trolley.data_transfer import (
    _get_copier,
    _get_deleter,
    configure,
    delete_data,
    transfer_data,
)


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset LRU caches and shim settings between tests."""
    with (
        shims.local.context.configure(shims.local.context.config()),
        shims.s3.context.configure(shims.s3.context.config()),
    ):
        yield
    _get_copier.cache_clear()
    _get_deleter.cache_clear()


# ── _get_copier ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "source,destination,expected",
    [
        (UPath("/src/file.txt"), UPath("/dst/file.txt"), shims.local.copy),
        (UPath("/src/file.txt"), UPath("s3://bucket/key"), shims.s3.upload),
        (UPath("s3://bucket/key"), UPath("/dst/file.txt"), shims.s3.download),
    ],
)
def test_choose_copier_type_supported_pairs(source, destination, expected):
    assert _get_copier(source, destination) is expected


def test_get_copier_gcs_source_raises():
    with pytest.raises(ValueError, match="No uploader found"):
        _get_copier(UPath("gs://bucket/key"), UPath("/dst/"))


def test_get_copier_s3_to_s3_raises():
    with pytest.raises(ValueError, match="No uploader found"):
        _get_copier(UPath("s3://bucket/src"), UPath("s3://bucket/dst"))


def test_get_copier_gcs_to_s3_raises():
    with pytest.raises(ValueError, match="No uploader found"):
        _get_copier(UPath("gs://bucket/key"), UPath("s3://bucket/dst"))


# ── transfer_data (local-to-local, real filesystem) ───────────────────────────


def test_transfer_data_copies_file(tmp_path):
    src = tmp_path / "src" / "file.txt"
    dst = tmp_path / "dst" / "file.txt"
    src.parent.mkdir()
    dst.parent.mkdir()
    src.write_text("hello")

    transfer_data(UPath(src), UPath(dst))

    assert dst.read_text() == "hello"


def test_transfer_data_copies_directory(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "a.txt").write_text("a")
    (src / "b.txt").write_text("b")

    transfer_data(UPath(src), UPath(dst))

    assert (dst / "a.txt").read_text() == "a"
    assert (dst / "b.txt").read_text() == "b"


def test_transfer_data_unsupported_pair_raises():
    with pytest.raises(ValueError):
        transfer_data(UPath("gs://bucket/key"), UPath("/dst/"))


# ── delete_data (local, real filesystem) ──────────────────────────────────────


def test_delete_data_deletes_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("data")
    delete_data(UPath(f))
    assert not f.exists()


def test_delete_data_deletes_directory_recursively(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    (d / "nested.txt").write_text("data")
    delete_data(UPath(d))
    assert not d.exists()


def test_delete_data_nonexistent_file_does_not_raise(tmp_path):
    delete_data(UPath(tmp_path / "nonexistent.txt"))


# ── _choose_deleter_type ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path,expected",
    [
        (UPath("/some/file.txt"), shims.local.delete),
        (UPath("s3://bucket/key"), shims.s3.delete),
        (UPath("gs://bucket/key"), shims.google.delete),
    ],
)
def test_get_deleter_supported_paths(path, expected):
    assert _get_deleter(path) is expected


def test_get_deleter_unsupported_raises():
    with pytest.raises(ValueError, match="No delete backend found"):
        _get_deleter(UPath("ftp://host/file"))


# ── configure ────────────────────────────────────────────────────────────────


def test_configure_permanent_applies_settings():
    configure(local=shims.local.LocalTransferSettings(copy_method="robocopy"))
    assert shims.local.context.config().copy_method == "robocopy"


def test_configure_context_manager_applies_inside():
    with configure(local=shims.local.LocalTransferSettings(copy_method="robocopy")):
        assert shims.local.context.config().copy_method == "robocopy"


def test_configure_context_manager_restores_outside():
    original = shims.local.context.config().copy_method
    with configure(local=shims.local.LocalTransferSettings(copy_method="robocopy")):
        pass
    assert shims.local.context.config().copy_method == original


def test_configure_no_args_is_noop():
    original = shims.local.context.config().copy_method
    with configure():
        assert shims.local.context.config().copy_method == original
    assert shims.local.context.config().copy_method == original


def test_configure_only_affects_specified_shims():
    original_local = shims.local.context.config().copy_method
    with configure(s3=shims.s3.S3TransferSettings()):
        assert shims.local.context.config().copy_method == original_local


def test_configure_nested_inner_takes_effect():
    with configure(local=shims.local.LocalTransferSettings(copy_method="robocopy")):
        with configure(local=shims.local.LocalTransferSettings(copy_method="shutil")):
            assert shims.local.context.config().copy_method == "shutil"


def test_configure_nested_outer_restored_after_inner():
    with configure(local=shims.local.LocalTransferSettings(copy_method="robocopy")):
        with configure(local=shims.local.LocalTransferSettings(copy_method="shutil")):
            pass
        assert shims.local.context.config().copy_method == "robocopy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

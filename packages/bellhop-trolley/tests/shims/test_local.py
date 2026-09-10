"""
Contract tests for the local shim.

Parametrized over copy_method so both shutil and robocopy backends
must satisfy the same directory-level behaviors. File-level tests only
run under shutil because robocopy operates on directories.
"""

import pytest

from bellhop_trolley.shims import local


@pytest.fixture(params=["shutil", "robocopy"])
def copy_method(request):
    with local.context.configure(copy_method=request.param):
        yield request.param


# ── copy: file ───────────────────────────────────────────────────────────────


def test_copy_file(source_file, tmp_path, copy_method):
    dst = tmp_path / "dst" / "file.txt"
    local.copy(source_file, dst)
    assert dst.read_text() == "hello"


def test_copy_file_creates_parent_dirs(source_file, tmp_path, copy_method):
    dst = tmp_path / "deep" / "nested" / "file.txt"
    local.copy(source_file, dst)
    assert dst.read_text() == "hello"


def test_copy_file_overwrites_existing(source_file, tmp_path, copy_method):
    dst = tmp_path / "dst" / "file.txt"
    dst.parent.mkdir()
    dst.write_text("old content")
    local.copy(source_file, dst)
    assert dst.read_text() == "hello"


# ── copy: directory (all backends) ───────────────────────────────────────────


def test_copy_directory_recursively(source_dir, tmp_path, copy_method):
    dst = tmp_path / "dst"
    local.copy(source_dir, dst)
    assert (dst / "a.txt").read_text() == "a"
    assert (dst / "subdir" / "b.txt").read_text() == "b"


def test_copy_directory_creates_parent_dirs(source_dir, tmp_path, copy_method):
    dst = tmp_path / "deep" / "nested" / "dst"
    local.copy(source_dir, dst)
    assert (dst / "a.txt").exists()


def test_copy_directory_preserves_nested_structure(source_dir, tmp_path, copy_method):
    dst = tmp_path / "dst"
    local.copy(source_dir, dst)
    assert (dst / "subdir").is_dir()
    assert (dst / "subdir" / "b.txt").exists()


# ── delete ───────────────────────────────────────────────────────────────────


def test_delete_file(source_file):
    local.delete(source_file)
    assert not source_file.exists()


def test_delete_directory_recursively(source_dir):
    local.delete(source_dir)
    assert not source_dir.exists()


def test_delete_nonexistent_file_is_noop(tmp_path):
    local.delete(tmp_path / "does_not_exist.txt")


def test_delete_nonexistent_dir_is_noop(tmp_path):
    local.delete(tmp_path / "does_not_exist_dir")


def test_delete_does_not_affect_siblings(source_dir):
    sibling = source_dir.parent / "sibling.txt"
    sibling.write_text("keep me")
    local.delete(source_dir / "a.txt")
    assert sibling.exists()

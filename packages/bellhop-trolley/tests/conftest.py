import os
from pathlib import Path
from typing import Optional

import pytest
from upath import UPath


@pytest.fixture
def example_data(tmp_path: Path) -> list[UPath]:
    data_dir = tmp_path / "data"
    paths = [
        data_dir / "file1.txt",
        data_dir / "file2.txt",
        data_dir / "dir1",
        data_dir / "dir2",
        data_dir / "dir2" / "file3.txt",
        data_dir / "dir2" / "subdir1" / "file4.txt",
    ]
    data_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
            path.write_text(f"Contents of {path.name}")
        else:
            path.mkdir(parents=True, exist_ok=True)
    return paths


def make_dummy_data(folder: Path, files: Optional[list[tuple[str, int]]] = None) -> list[Path]:
    """Make some random data files for testing."""

    if files is None:
        files = [("test.txt", 50), ("test2.txt", 50), ("directory/test.txt", 50)]

    files_actual = []
    for item, size_mb in files:
        path = folder / item
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(os.urandom(size_mb * 1_000_000))
        files_actual.append(path)

    return files_actual


@pytest.fixture
def dummy_file(tmp_path: Path) -> Path:
    return make_dummy_data(tmp_path, [("dummy.txt", 20)])[0]


@pytest.fixture
def dummy_data_directory(tmp_path: Path):
    make_dummy_data(tmp_path)[0]
    return tmp_path

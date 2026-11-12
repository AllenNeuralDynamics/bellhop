import os
from datetime import datetime
from pathlib import Path

import pytest
from bellhop_models.specifications import CommandTask, JobSpecification, RunProgramParams


def make_dummy_data(folder: Path, files: list[tuple[str, int]] | None = None) -> list[Path]:
    """Make some random data files for testing."""

    if files is None:
        files = [("test.txt", 50), ("test2.txt", 50), ("directory/test.txt", 50)]

    files_actual = []
    for item, size_mb in files:
        path = folder / item
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(os.urandom(size_mb * 1_000_000))
        files_actual.append(str(path))

    return files_actual


@pytest.fixture()
def dummy_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Pytest fixture: returns a temporary directory filled with dummy test data.

    Usage:
        def test_something(dummy_data_dir: Path):
            assert (dummy_data_dir / "files" / "small.txt").exists()
    """
    path = tmp_path_factory.mktemp("dummy_data")
    files = make_dummy_data(path)
    return path


@pytest.fixture
def sample_job():
    """Create a sample Job with tasks."""
    return JobSpecification(
        name="Sample Job",
        description="Example used in unit tests",
        custom_fields={"field1": "value1", "field2": "value2"},
        tasks=[
            CommandTask(
                name="Task 1",
                parameters=RunProgramParams(program="echo", arguments=["Hello from task 1"]),
            ),
            CommandTask(
                name="Task 2",
                parameters=RunProgramParams(program="echo", arguments=["Hello from task 2"]),
            ),
        ],
        time_scheduled=datetime(2026, 1, 10, 14, 30),
    )

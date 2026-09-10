import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from bellhop_models.database import TaskStates
from bellhop_models.specifications import JobSpecification, SubprocessTask

from bellhop.task_executors import RunSubprocessParams


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
def temp_db(monkeypatch, tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_bellhop.json"
    monkeypatch.setattr(db_old, "DATABASE_FILE", str(db_path))
    db_old.init_db()
    return db_path


# @pytest.fixture
# def sample_Job():
#     """Create a sample Job with tasks."""
#     return Job(
#         name="Sample Job",
#         description="Example used in unit tests",
#         custom_fields={"field1": "value1", "field2": "value2"},
#         tasks=[
#             Task(name="Task 1", program="Subprocess", args=["echo", "Hello from task 1"]),
#             Task(name="Task 2", program="Subprocess", args=["echo", "Hello from task 2"]),
#         ],
#         scheduled_execution=datetime(2026, 1, 10, 14, 30),
#     )


@pytest.fixture
def sample_Job():
    """Create a sample Job with tasks."""
    return JobSpecification(
        name="Sample Job",
        description="Example used in unit tests",
        custom_fields={"field1": "value1", "field2": "value2"},
        tasks=[
            SubprocessTask(
                name="Task 1",
                parameters=RunSubprocessParams(program="echo", command=["Hello from task 1"]),
            ),
            SubprocessTask(
                name="Task 2",
                parameters=RunSubprocessParams(program="echo", command=["Hello from task 2"]),
            ),
        ],
        time_scheduled=datetime(2026, 1, 10, 14, 30),
    )


@pytest.fixture
def multiple_Jobs():
    """Create multiple Jobs with different states."""
    base_time = datetime(2026, 1, 6, 12, 0)
    Jobs = []
    states: list[TaskStates] = ["Not Started", "In Progress", "Completed", "Errored"]

    for n in range(8):
        Jobs.append(
            JobSpecification(
                name=f"Job {n}",
                description=f"Description for Job {n}",
                custom_fields={"even": n % 2 == 0, "number": n},
                tasks=[
                    SubprocessTask(
                        name=f"Task for Job {n}",
                        parameters=RunSubprocessParams(program="echo", command=[f"Hello from Job {n}"]),
                    )
                ],
                time_scheduled=base_time + timedelta(hours=n),
                state=states[n % len(states)],
            )
        )

    return Jobs

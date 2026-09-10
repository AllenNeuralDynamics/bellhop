"""Self-test that submits a dummy job to a running Bellhop API and waits for it to complete.

The job creates dummy data via a subprocess, copies it to a second location, then deletes both.
"""

import os
import tempfile
import time
import uuid
from pathlib import Path

from bellhop_client import client
from bellhop_models.specifications import (
    DeleteDataParams,
    DeleteDataTask,
    JobSpecification,
    RunSubprocessParams,
    SubprocessTask,
    TransferDataParams,
    TransferDataTask,
)


def _make_dummy_data(folder: Path) -> None:
    files = [
        "file1.txt",
        "file2.txt",
        "dir1/file3.txt",
        "dir2/file4.txt",
        "dir2/subdir1/file5.txt",
    ]
    for name in files:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(os.urandom(50 * 1_000))


def _make_job_spec(
    label: str,
    custom_fields: dict,
    source_dir: Path,
    dest_dir: Path,
) -> JobSpecification:
    """Build a JobSpecification that moves pre-created files, then deletes both locations."""

    echo_task = SubprocessTask(
        name="Echo",
        parameters=RunSubprocessParams(
            program="echo",
            command=["Hello from bellhop self-test"],
        ),
    )

    move_task = TransferDataTask(
        name="Move data",
        parameters=TransferDataParams(
            source=str(source_dir),
            destination=str(dest_dir),
        ),
    )

    verify_task = SubprocessTask(
        name="Verify destination",
        parameters=RunSubprocessParams(
            program="dir",
            command=["/b", "/s", str(dest_dir)],
        ),
    )

    delete_source_task = DeleteDataTask(
        name="Delete source dir",
        parameters=DeleteDataParams(source=str(source_dir)),
    )

    delete_dest_task = DeleteDataTask(
        name="Delete dest dir",
        parameters=DeleteDataParams(source=str(dest_dir)),
    )

    return JobSpecification(
        name=f"Bellhop self-test [{label}]",
        description="Automated self-test job",
        custom_fields={"self_test": True, **custom_fields},
        tasks=[echo_task, move_task, verify_task, delete_source_task, delete_dest_task],
    )


def _wait_for_terminal(job_id: uuid.UUID, timeout: float):
    """Poll until the job reaches Completed or Errored, then return the Job."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get_job(job_id)
        if job.state in ("Completed", "Errored"):
            return job
        time.sleep(0.5)
    raise TimeoutError(f"Self-test job {job_id} did not finish within {timeout}s")


def run_self_test(
    *,
    working_dir: Path | None = None,
    label: str = "default",
    timeout: float = 60.0,
    custom_fields: dict | None = None,
):
    """Submit a dummy job to the Bellhop API and wait for it to complete."""
    if custom_fields is None:
        custom_fields = {}

    root = working_dir or Path(tempfile.gettempdir())
    run_id = uuid.uuid4().hex[:8]
    source_dir = root / f"bellhop_selftest_{run_id}_src"
    dest_dir = root / f"bellhop_selftest_{run_id}_dst"
    source_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    _make_dummy_data(source_dir)

    job_spec = _make_job_spec(
        label=label,
        custom_fields=custom_fields,
        source_dir=source_dir,
        dest_dir=dest_dir,
    )
    job_id = client.submit_job(job_spec)
    print(f"Self-test job submitted: {job_id}")

    job = _wait_for_terminal(job_id, timeout)
    print(f"Self-test job finished: {job.state}")

    if job.state != "Completed":
        failed = next((h for h in job.history if h.success is False), None)
        detail = failed.message if failed else "unknown"
        raise RuntimeError(f"Self-test job {job_id} ended in state '{job.state}': {detail}")

    return job


if __name__ == "__main__":
    run_self_test()

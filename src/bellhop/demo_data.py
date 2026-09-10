"""A variety of realistic jobs for tests and local demos.

Generate a demo database file with: `uv run bellhop demo-db ./demo_jobs.db`
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from bellhop_models.database import Job, TaskExecution, TaskStates
from bellhop_models.specifications import (
    DeleteDataParams,
    DeleteDataTask,
    HTTPRequestParams,
    HTTPRequestTask,
    JobSpecification,
    RunSubprocessParams,
    SendMessageParams,
    SendMessageTask,
    SubprocessTask,
    TransferDataListParams,
    TransferDataParams,
    TransferDataTask,
)

from bellhop.db import Database

BASE_TIME = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def _at(days: float = 0, hours: float = 0) -> datetime:
    return BASE_TIME + timedelta(days=days, hours=hours)


def demo_job_specs() -> list[JobSpecification]:
    """Job specifications covering every task type, spread across a date range."""
    return [
        JobSpecification(
            name="Mesoscope Session Upload",
            description="Nightly upload of mesoscope session data to the archive",
            custom_fields={"rig": "MESO-1", "subject": "654321", "priority": "high"},
            time_scheduled=_at(days=0),
            tasks=[
                SubprocessTask(
                    name="Checksum source",
                    description="Verify integrity before transfer",
                    parameters=RunSubprocessParams(program="python", command=["-m", "hashlib_check", "/data/meso"]),
                ),
                TransferDataTask(
                    name="Upload to archive",
                    parameters=TransferDataParams(
                        source="/data/meso/654321", destination="s3://aind-archive/meso/654321"
                    ),
                ),
                SendMessageTask(
                    name="Notify operators",
                    parameters=SendMessageParams(
                        recipient="ops@example.org",
                        subject="Mesoscope upload complete",
                        body="Session 654321 uploaded successfully.",
                    ),
                ),
            ],
        ),
        JobSpecification(
            name="Ephys Backup",
            description="Weekly backup of ephys rig data",
            custom_fields={"rig": "EPHYS-3", "retention_days": 90},
            time_scheduled=_at(days=1),
            tasks=[
                TransferDataTask(
                    name="Copy raw data",
                    parameters=TransferDataListParams(
                        source=["session_a", "session_b"],
                        source_base_dir="/data/ephys",
                        destination="//allen/backup/ephys",
                        parallel=True,
                    ),
                ),
                DeleteDataTask(
                    name="Clear staging",
                    parameters=DeleteDataParams(source="/data/ephys/staging"),
                ),
            ],
        ),
        JobSpecification(
            name="Behavior Data Sync",
            description="Sync behavior boxes to cloud storage",
            custom_fields={"rig": "BEH-12"},
            time_scheduled=_at(days=2),
            tasks=[
                TransferDataTask(
                    name="Sync to S3",
                    parameters=TransferDataParams(source="/data/behavior", destination="s3://aind-behavior/raw"),
                ),
                HTTPRequestTask(
                    name="Register in metadata service",
                    parameters=HTTPRequestParams(
                        url="https://metadata.example.org/api/sessions",
                        method="POST",
                        headers={"Content-Type": "application/json"},
                        data={"rig": "BEH-12", "status": "uploaded"},
                    ),
                ),
            ],
        ),
        JobSpecification(
            name="Archive Cleanup",
            description="Delete staging data older than the retention window",
            custom_fields={"retention_days": 30},
            time_scheduled=_at(days=3),
            tasks=[
                DeleteDataTask(
                    name="Purge old staging",
                    parameters=DeleteDataParams(source="/data/staging/expired"),
                ),
            ],
        ),
        JobSpecification(
            name="Smartspim Transfer",
            description="Move lightsheet volumes to the cluster",
            custom_fields={"rig": "SMARTSPIM-2", "priority": "low"},
            time_scheduled=_at(days=4),
            tasks=[
                TransferDataTask(
                    name="Move volumes",
                    parameters=TransferDataParams(source="/data/smartspim", destination="//allen/scratch/smartspim"),
                ),
                SubprocessTask(
                    name="Kick off processing",
                    parameters=RunSubprocessParams(program="sbatch", command=["process_smartspim.sh"]),
                ),
            ],
        ),
        JobSpecification(
            name="Nightly Health Check",
            time_scheduled=_at(days=5),
            tasks=[
                HTTPRequestTask(
                    name="Ping API",
                    parameters=HTTPRequestParams(url="https://bellhop.example.org/health"),
                ),
            ],
        ),
        JobSpecification(
            name="Quarterly Report",
            description="Generate and email the quarterly transfer report",
            custom_fields={"audience": "leadership"},
            time_scheduled=_at(days=6),
            tasks=[
                SubprocessTask(
                    name="Build report",
                    parameters=RunSubprocessParams(program="python", command=["-m", "reports.quarterly"]),
                ),
                SendMessageTask(
                    name="Email report",
                    parameters=SendMessageParams(
                        recipient="leadership@example.org",
                        subject="Quarterly transfer report",
                        body="See attached summary.",
                    ),
                ),
            ],
        ),
        JobSpecification(
            name="Ad Hoc Restore",
            description="Restore a single session from cold storage on request",
            time_scheduled=_at(days=7),
            tasks=[
                TransferDataTask(
                    name="Restore from glacier",
                    parameters=TransferDataParams(
                        source="s3://aind-cold/meso/123456", destination="/data/restore/123456"
                    ),
                ),
            ],
        ),
    ]


# (job state, number of tasks that already ran, failure message for the last run)
_STATE_PLAN: list[tuple[TaskStates, int, str | None]] = [
    ("Completed", 3, None),
    ("Errored", 2, "Destination unreachable: //allen/backup/ephys"),
    ("In Progress", 1, None),
    ("Completed", 1, None),
    ("Not Started", 0, None),
    ("Completed", 1, None),
    ("Not Started", 0, None),
    ("Errored", 1, "Object not found in cold storage"),
]


def _record_history(db: Database, job: Job, ran: int, failure: str | None) -> None:
    """Mark the first `ran` tasks as executed, failing the last one if `failure` is set."""
    for index, task in enumerate(job.tasks[:ran]):
        failed = failure is not None and index == ran - 1
        task.state = "Errored" if failed else "Completed"
        db.update_task(task)
        db.add_execution(
            TaskExecution(
                task=task,
                success=not failed,
                message=failure if failed else None,
                time_started=job.next_execution_time + timedelta(minutes=10 * index),
                time_ended=job.next_execution_time + timedelta(minutes=10 * index + 5),
                logs=failure if failed else f"{task.name} finished without errors.",
            )
        )

    if job.state == "In Progress" and ran < len(job.tasks):
        current = job.tasks[ran]
        current.state = "In Progress"
        db.update_task(current)


def populate(db: Database) -> list[Job]:
    """Add the demo jobs to an existing database."""
    jobs = []
    for spec, (state, ran, failure) in zip(demo_job_specs(), _STATE_PLAN, strict=True):
        job = Job.from_specification(spec)
        job.state = state
        job.next_task = None if state == "Completed" else ran
        created = db.create_job(job)
        _record_history(db, created, ran, failure)
        jobs.append(db.get_job(created.id))
    return jobs


def create_demo_database(db_file: str = ":memory:", overwrite: bool = False) -> Database:
    """Build a database populated with the demo jobs."""
    if db_file != ":memory:":
        path = Path(db_file)
        if path.exists():
            if not overwrite:
                raise FileExistsError(f"{path} already exists; pass overwrite=True to replace it")
            path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)

    db = Database(db_file)
    populate(db)
    return db

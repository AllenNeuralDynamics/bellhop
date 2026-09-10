"""Tests for the Engine class.

Fast tests schedule jobs far in the future so the scheduler never fires them.
Execution tests submit with an immediate trigger and poll until done.
"""

import sys
import time
import uuid
from datetime import datetime, timedelta

import pytest
from bellhop_models.database import Job
from bellhop_models.specifications import JobSpecification, RunSubprocessParams, SubprocessTask

from bellhop.db import Database
from bellhop.engine import Engine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path):
    e = Engine(db_file=str(tmp_path / "test.db")).start()
    yield e
    e.shutdown()


@pytest.fixture
def pending_job_spec():
    return JobSpecification(
        name="Pending Job",
        tasks=[
            SubprocessTask(
                name="Echo",
                parameters=RunSubprocessParams(
                    program=sys.executable,
                    command=["-c", "print('hello', flush=True)"],
                ),
            )
        ],
        time_scheduled=datetime.now() + timedelta(hours=1),
    )


@pytest.fixture
def two_task_spec():
    return JobSpecification(
        name="Two Task Job",
        tasks=[
            SubprocessTask(
                name="Step 1",
                parameters=RunSubprocessParams(
                    program=sys.executable,
                    command=["-c", "print('step 1', flush=True)"],
                ),
            ),
            SubprocessTask(
                name="Step 2",
                parameters=RunSubprocessParams(
                    program=sys.executable,
                    command=["-c", "print('step 2', flush=True)"],
                ),
            ),
        ],
        time_scheduled=datetime.now(),
    )


def _wait_for_terminal(job_id, engine: Engine, timeout=20) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = engine.db.get_job(job_id)
        if job and job.state in ("Completed", "Errored"):
            return job.state
        time.sleep(0.1)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")


# ---------------------------------------------------------------------------
# submit_job
# ---------------------------------------------------------------------------


def test_submit_job_returns_uuid(engine, pending_job_spec):
    job_id = engine.submit_job(pending_job_spec)
    assert isinstance(job_id, uuid.UUID)


def test_submit_job_persists_to_db(engine, pending_job_spec):
    job_id = engine.submit_job(pending_job_spec)
    job = engine.db.get_job(job_id)
    assert job.id == job_id
    assert job.name == "Pending Job"
    assert job.state == "Not Started"


def test_submit_job_registers_in_scheduler(engine, pending_job_spec):
    job_id = engine.submit_job(pending_job_spec)
    assert engine._scheduler.get_job(str(job_id)) is not None


# ---------------------------------------------------------------------------
# abort_job
# ---------------------------------------------------------------------------


def test_abort_pending_job_marks_errored(engine, pending_job_spec):
    job_id = engine.submit_job(pending_job_spec)
    engine.abort_job(job_id)
    job = engine.db.get_job(job_id)
    assert job.state == "Errored"


def test_abort_pending_job_removes_from_scheduler(engine, pending_job_spec):
    job_id = engine.submit_job(pending_job_spec)
    engine.abort_job(job_id)
    assert engine._scheduler.get_job(str(job_id)) is None


def test_abort_missing_job_raises(engine):
    with pytest.raises(KeyError):
        engine.abort_job(uuid.uuid4())


# ---------------------------------------------------------------------------
# update_job
# ---------------------------------------------------------------------------


def test_update_job_persists_to_db(engine, pending_job_spec):
    job_id = engine.submit_job(pending_job_spec)
    job = engine.db.get_job(job_id)
    job.name = "Renamed"
    engine.update_job(job)
    fetched = engine.db.get_job(job_id)
    assert fetched.name == "Renamed"


# ---------------------------------------------------------------------------
# Execution (spawn a real subprocess)
# ---------------------------------------------------------------------------


def test_job_runs_to_completion(engine, two_task_spec):
    job_id = engine.submit_job(two_task_spec)
    assert _wait_for_terminal(job_id, engine) == "Completed"


def test_completed_job_task_states(engine, two_task_spec):
    job_id = engine.submit_job(two_task_spec)
    _wait_for_terminal(job_id, engine)
    job = engine.db.get_job(job_id)
    assert all(t.state == "Completed" for t in job.tasks)


def test_completed_job_has_execution_logs(engine, two_task_spec):
    job_id = engine.submit_job(two_task_spec)
    _wait_for_terminal(job_id, engine)
    job = engine.db.get_job(job_id)
    assert len(job.history) == 2
    assert all(e.success is True for e in job.history)
    assert any("step 1" in e.logs for e in job.history)
    assert any("step 2" in e.logs for e in job.history)


def test_failing_task_marks_job_errored(engine):
    spec = JobSpecification(
        name="Failing Job",
        tasks=[
            SubprocessTask(
                name="Bad command",
                parameters=RunSubprocessParams(
                    program=sys.executable,
                    command=["-c", "raise SystemExit(1)"],
                ),
            )
        ],
        time_scheduled=datetime.now(),
    )
    job_id = engine.submit_job(spec)
    assert _wait_for_terminal(job_id, engine) == "Errored"


def test_failing_task_stores_error_message(engine):
    spec = JobSpecification(
        name="Failing Job",
        tasks=[
            SubprocessTask(
                name="Bad command",
                parameters=RunSubprocessParams(
                    program=sys.executable,
                    command=["-c", "raise SystemExit(1)"],
                ),
            )
        ],
        time_scheduled=datetime.now(),
    )
    job_id = engine.submit_job(spec)
    _wait_for_terminal(job_id, engine)
    job = engine.db.get_job(job_id)
    assert job.history[0].success is False
    assert job.history[0].message is not None


def test_second_task_not_run_after_failure(engine):
    spec = JobSpecification(
        name="Fail Then Stop",
        tasks=[
            SubprocessTask(
                name="Fail",
                parameters=RunSubprocessParams(
                    program=sys.executable,
                    command=["-c", "raise SystemExit(1)"],
                ),
            ),
            SubprocessTask(
                name="Should not run",
                parameters=RunSubprocessParams(
                    program=sys.executable,
                    command=["-c", "print('should not appear')"],
                ),
            ),
        ],
        time_scheduled=datetime.now(),
    )
    job_id = engine.submit_job(spec)
    _wait_for_terminal(job_id, engine)
    job = engine.db.get_job(job_id)
    assert len(job.history) == 1  # only first task executed
    assert job.tasks[1].state == "Not Started"


# ---------------------------------------------------------------------------
# start / _reschedule_pending_jobs
# ---------------------------------------------------------------------------


def test_start_reschedules_pending_jobs_left_in_db(tmp_path):
    """Jobs left "Not Started" in the DB (e.g. after a restart) should be re-added on start()."""
    db_file = str(tmp_path / "test.db")
    spec = JobSpecification(
        name="Left Over Job",
        tasks=[
            SubprocessTask(
                name="Echo",
                parameters=RunSubprocessParams(
                    program=sys.executable,
                    command=["-c", "print('hello', flush=True)"],
                ),
            )
        ],
        time_scheduled=datetime.now() - timedelta(days=1),
    )
    job = Job.from_specification(spec)
    Database(db_file).create_job(job)

    engine = Engine(db_file=db_file).start()
    try:
        assert engine._scheduler.get_job(str(job.id)) is not None
    finally:
        engine.shutdown()


def test_start_runs_pending_job_left_in_db_to_completion(tmp_path):
    db_file = str(tmp_path / "test.db")
    spec = JobSpecification(
        name="Left Over Job",
        tasks=[
            SubprocessTask(
                name="Echo",
                parameters=RunSubprocessParams(
                    program=sys.executable,
                    command=["-c", "print('hello', flush=True)"],
                ),
            )
        ],
        time_scheduled=datetime.now() - timedelta(days=1),
    )
    job = Job.from_specification(spec)
    Database(db_file).create_job(job)

    engine = Engine(db_file=db_file).start()
    try:
        assert _wait_for_terminal(job.id, engine) == "Completed"
    finally:
        engine.shutdown()

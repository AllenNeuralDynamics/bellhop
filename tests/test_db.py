import uuid
from datetime import datetime

import pytest
from bellhop_models.database import Job, TaskExecution
from bellhop_models.specifications import JobSpecification, RunSubprocessParams, SubprocessTask

from bellhop.db import Database


@pytest.fixture
def database() -> Database:
    return Database(":memory:")


@pytest.fixture
def sample_job() -> Job:
    spec = JobSpecification(
        name="Test Job",
        description="A test job",
        custom_fields={"env": "test"},
        tasks=[
            SubprocessTask(
                name="Echo Task",
                parameters=RunSubprocessParams(program="echo", command=["hello"]),
            ),
            SubprocessTask(
                name="Second Task",
                parameters=RunSubprocessParams(program="echo", command=["world"]),
            ),
        ],
        time_scheduled=datetime(2026, 6, 1, 9, 0),
    )
    return Job.from_specification(spec)


def make_job(name: str, description: str | None = None, day: int = 1) -> Job:
    return Job.from_specification(
        JobSpecification(
            name=name,
            description=description,
            tasks=[SubprocessTask(name="T", parameters=RunSubprocessParams(program="echo", command=[]))],
            time_scheduled=datetime(2026, 6, day, 9, 0),
        )
    )


@pytest.fixture
def query_jobs_db(database) -> Database:
    for job in (
        make_job("Alpha Import", "Nightly backup", day=1),
        make_job("Daily ETL", "Runs ALPHA migration", day=2),
        make_job("Beta Export", "Nothing to see", day=3),
        make_job("Gamma Sync", None, day=4),
    ):
        database.create_job(job)
    return database


# --- create_job ---


def test_create_job_round_trip(database, sample_job):
    database.create_job(sample_job)
    fetched = database.get_job(sample_job.id)
    assert fetched.model_dump(mode="json") == sample_job.model_dump(mode="json")


def test_get_job_returns_none_for_missing(database):
    assert database.get_job(uuid.uuid4()) is None


def test_list_jobs_empty(database):
    assert database.list_jobs() == []


def test_list_jobs_returns_all(database, sample_job):
    database.create_job(sample_job)
    database.create_job(make_job("Second Job", day=2))
    results = database.list_jobs()
    assert {j.name for j in results} == {"Test Job", "Second Job"}


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({}, {"Alpha Import", "Daily ETL", "Beta Export", "Gamma Sync"}),
        ({"name_contains": "alpha"}, {"Alpha Import"}),
        ({"name_contains": "missing"}, set()),
        ({"description_contains": "backup"}, {"Alpha Import"}),
        ({"text_contains": "alpha"}, {"Alpha Import", "Daily ETL"}),
        ({"name_contains": "  "}, {"Alpha Import", "Daily ETL", "Beta Export", "Gamma Sync"}),
        (
            {"scheduled_from": datetime(2026, 6, 2, 9, 0), "scheduled_to": datetime(2026, 6, 3, 9, 0)},
            {"Daily ETL", "Beta Export"},
        ),
        ({"scheduled_from": datetime(2026, 6, 3, 9, 0)}, {"Beta Export", "Gamma Sync"}),
        ({"scheduled_to": datetime(2026, 6, 2, 9, 0)}, {"Alpha Import", "Daily ETL"}),
        ({"text_contains": "alpha", "scheduled_from": datetime(2026, 6, 2, 9, 0)}, {"Daily ETL"}),
    ],
)
def test_query_jobs_filters(query_jobs_db, filters, expected):
    assert {job.name for job in query_jobs_db.query_jobs(**filters)} == expected


def test_query_jobs_rejects_invalid_date_range(database):
    with pytest.raises(ValueError):
        database.query_jobs(
            scheduled_from=datetime(2026, 6, 3, 9, 0),
            scheduled_to=datetime(2026, 6, 2, 9, 0),
        )


def test_update_job(database, sample_job):
    database.create_job(sample_job)
    sample_job.state = "In Progress"
    sample_job.next_task = 1
    sample_job.custom_fields = {"env": "prod"}
    database.update_job(sample_job)
    fetched = database.get_job(sample_job.id)
    assert fetched.model_dump(mode="json") == sample_job.model_dump(mode="json")


def test_update_job_not_found(database, sample_job):
    with pytest.raises(KeyError):
        database.update_job(sample_job)


def test_delete_job(database, sample_job):
    database.create_job(sample_job)
    database.delete_job(sample_job.id)
    assert database.get_job(sample_job.id) is None


def test_delete_job_cascades_tasks(database, sample_job):
    created = database.create_job(sample_job)
    task_id = created.tasks[0].id
    database.delete_job(sample_job.id)
    assert database.get_task(task_id) is None


def test_delete_job_not_found(database):
    with pytest.raises(KeyError):
        database.delete_job(uuid.uuid4())


def test_get_task(database, sample_job):
    created = database.create_job(sample_job)
    fetched = database.get_task(created.tasks[0].id)
    assert fetched == created.tasks[0]


def test_get_task_returns_none_for_missing(database):
    assert database.get_task(uuid.uuid4()) is None


def test_update_task(database, sample_job):
    created = database.create_job(sample_job)
    task = created.tasks[0]
    task.state = "Completed"
    database.update_task(task)
    fetched = database.get_task(task.id)
    assert fetched == task


def test_update_task_not_found(database, sample_job):
    with pytest.raises(KeyError):
        database.update_task(sample_job.tasks[0])


def test_add_execution(database, sample_job):
    created = database.create_job(sample_job)
    task = created.tasks[0]
    execution = TaskExecution(
        task=task,
        success=True,
        time_started=datetime(2026, 6, 1, 9, 0),
        time_ended=datetime(2026, 6, 1, 9, 1),
        logs="all good",
    )
    database.add_execution(execution)
    job = database.get_job(created.id)
    assert len(job.history) == 1
    assert job.history[0].model_dump(mode="json") == execution.model_dump(mode="json")


def test_add_execution_failure(database, sample_job):
    created = database.create_job(sample_job)
    task = created.tasks[0]
    execution = TaskExecution(
        task=task,
        success=False,
        message="timed out",
        time_started=datetime(2026, 6, 1, 9, 0),
        time_ended=datetime(2026, 6, 1, 9, 5),
        logs="stderr output",
    )
    database.add_execution(execution)
    job = database.get_job(created.id)
    assert len(job.history) == 1
    assert job.history[0].model_dump(mode="json") == execution.model_dump(mode="json")

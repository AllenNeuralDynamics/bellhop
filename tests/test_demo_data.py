import pytest

from bellhop.demo_data import create_demo_database, demo_job_specs


@pytest.fixture
def demo_db():
    return create_demo_database(":memory:")


def test_demo_database_contains_all_jobs(demo_db):
    assert len(demo_db.list_jobs()) == len(demo_job_specs())


def test_demo_database_covers_every_task_type(demo_db):
    task_types = {task.task_type for job in demo_db.list_jobs() for task in job.tasks}
    assert task_types == {"Move Data", "Delete Data", "Send Message", "Subprocess", "HTTP Request"}


def test_demo_database_covers_every_job_state(demo_db):
    assert {job.state for job in demo_db.list_jobs()} == {
        "Not Started",
        "In Progress",
        "Completed",
        "Errored",
    }


def test_demo_database_has_successful_and_failed_history(demo_db):
    outcomes = {execution.success for job in demo_db.list_jobs() for execution in job.history}
    assert outcomes == {True, False}


def test_demo_database_is_queryable_by_text_and_date(demo_db):
    assert {job.name for job in demo_db.query_jobs(text_contains="backup")} == {
        "Mesoscope Session Upload",
        "Ephys Backup",
    }


def test_create_demo_database_file(tmp_path):
    db_file = tmp_path / "demo_jobs.db"
    create_demo_database(str(db_file))
    assert db_file.exists()

    with pytest.raises(FileExistsError):
        create_demo_database(str(db_file))

    create_demo_database(str(db_file), overwrite=True)

"""API route tests.

Uses FastAPI's TestClient with dependency overrides so each test gets a real
Engine and TemplateManager backed by a tmp dir, without running the lifespan
(which would also start the dropbox watcher and scheduler side effects).
"""

import uuid
from datetime import datetime, timedelta

import pytest
from bellhop_models.specifications import CommandTask, JobSpecification, RunCommandParams
from fastapi.testclient import TestClient

from bellhop.api import app, get_engine, get_template_manager
from bellhop.config import Config
from bellhop.engine import Engine
from bellhop.job_templates import TemplateManager


@pytest.fixture
def client(tmp_path):
    engine = Engine(db_file=str(tmp_path / "test.db")).start()
    config = Config(data_dir=tmp_path)
    manager = TemplateManager(config)

    app.state.config = config
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_template_manager] = lambda: manager

    yield TestClient(app)

    app.dependency_overrides.clear()
    engine.shutdown()


@pytest.fixture
def future_job_spec() -> JobSpecification:
    # Scheduled far ahead so the scheduler never fires it during the test.
    return JobSpecification(
        name="API Test Job",
        tasks=[
            CommandTask(
                name="Echo",
                parameters=RunCommandParams(command="echo hi"),
            )
        ],
        time_scheduled=datetime.now() + timedelta(days=1),
    )


# ---------------------------------------------------------------------------
# Health / environment
# ---------------------------------------------------------------------------


def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_environment(client):
    response = client.get("/environment")
    assert response.status_code == 200
    assert set(response.json()) == set(app.state.config.env_vars_to_show)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


def test_list_jobs_empty(client):
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json() == []


def test_submit_and_get_job(client, future_job_spec):
    submit = client.post("/jobs", json=future_job_spec.model_dump(mode="json"))
    assert submit.status_code == 201
    job_id = submit.json()

    fetched = client.get(f"/jobs/{job_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "API Test Job"


def test_get_job_not_found(client):
    response = client.get(f"/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


def test_abort_missing_job(client):
    response = client.delete(f"/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def test_list_templates_includes_self_test(client):
    response = client.get("/templates")
    assert response.status_code == 200
    assert "self_test_template" in response.json()


def test_create_and_get_template(client):
    content = "name: n\ntasks: []\n"
    created = client.post("/templates/mytemplate", params={"body": content})
    assert created.status_code == 201

    fetched = client.get("/templates/mytemplate")
    assert fetched.status_code == 200
    assert fetched.json() == content


def test_create_template_conflict(client):
    client.post("/templates/dup", params={"body": "name: n\ntasks: []\n"})
    again = client.post("/templates/dup", params={"body": "name: other\ntasks: []\n"})
    assert again.status_code == 409


def test_get_template_not_found(client):
    response = client.get("/templates/does_not_exist")
    assert response.status_code == 404


def test_get_template_variables(client):
    client.post("/templates/vars", params={"body": "name: {{ job_name }}\ndir: {{ data_dir }}\ntasks: []\n"})
    response = client.get("/templates/vars/variables")
    assert response.status_code == 200
    assert set(response.json()) == {"job_name", "data_dir"}


def test_get_template_defaults(client):
    client.post("/templates/defs", params={"body": "dir: {{ data_dir | default('C:/data') }}\ntasks: []\n"})
    response = client.get("/templates/defs/defaults")
    assert response.status_code == 200
    assert response.json() == {"data_dir": "C:/data"}


def test_get_template_defaults_not_found(client):
    response = client.get("/templates/missing/defaults")
    assert response.status_code == 404


def test_update_template_not_found(client):
    response = client.put("/templates/nope", params={"body": "name: n\ntasks: []\n"})
    assert response.status_code == 404


def test_delete_template(client):
    client.post("/templates/gone", params={"body": "name: n\ntasks: []\n"})
    deleted = client.delete("/templates/gone")
    assert deleted.status_code == 204
    assert client.get("/templates/gone").status_code == 404


def test_delete_template_not_found(client):
    response = client.delete("/templates/nope")
    assert response.status_code == 404

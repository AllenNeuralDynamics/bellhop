import time

import pytest
import yaml

from bellhop.dropbox import JobDropbox, _DropboxHandler
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
def dropbox_dirs(tmp_path):
    dropbox = tmp_path / "dropbox"
    submitted = dropbox / "submitted"
    failed = dropbox / "failed_submissions"
    dropbox.mkdir()
    submitted.mkdir()
    failed.mkdir()
    return dropbox, submitted, failed


@pytest.fixture
def handler(engine, dropbox_dirs):
    _, submitted, failed = dropbox_dirs
    return _DropboxHandler(engine, submitted, failed)


VALID_SPEC = {
    "name": "Dropbox Test Job",
    "tasks": [
        {
            "name": "Echo",
            "task_type": "Subprocess",
            "parameters": {"program": "python", "command": ["-c", "print('hi')"]},
        }
    ],
}


# ---------------------------------------------------------------------------
# Unit tests — _DropboxHandler._process
# ---------------------------------------------------------------------------


def test_valid_yaml_submits_job(engine, handler, dropbox_dirs):
    dropbox, submitted, _ = dropbox_dirs
    spec_file = dropbox / "job.yml"
    spec_file.write_text(yaml.dump(VALID_SPEC))

    handler._process(spec_file)

    assert not spec_file.exists()
    assert (submitted / "job.yml").exists()
    assert len(engine.db.list_jobs()) == 1


def test_valid_yaml_job_has_correct_name(engine, handler, dropbox_dirs):
    dropbox, _, _ = dropbox_dirs
    spec_file = dropbox / "job.yaml"
    spec_file.write_text(yaml.dump(VALID_SPEC))

    handler._process(spec_file)

    job = engine.db.list_jobs()[0]
    assert job.name == "Dropbox Test Job"


def test_invalid_yaml_moves_to_failed(engine, handler, dropbox_dirs):
    dropbox, submitted, failed = dropbox_dirs
    spec_file = dropbox / "bad.yml"
    spec_file.write_text("not: valid: yaml: [[[")

    handler._process(spec_file)

    assert not spec_file.exists()
    assert (failed / "bad.yml").exists()
    assert len(engine.db.list_jobs()) == 0


def test_invalid_spec_writes_error_file(engine, handler, dropbox_dirs):
    dropbox, _, failed = dropbox_dirs
    spec_file = dropbox / "bad.yml"
    spec_file.write_text(yaml.dump({"name": "Missing tasks"}))  # missing required field

    handler._process(spec_file)

    assert (failed / "bad.error.txt").exists()
    assert (failed / "bad.error.txt").read_text()


def test_non_yaml_file_ignored(engine, handler, dropbox_dirs):
    dropbox, submitted, _ = dropbox_dirs
    txt_file = dropbox / "notes.txt"
    txt_file.write_text("ignore me")

    # on_created should skip non-.yml/.yaml files
    from watchdog.events import FileCreatedEvent

    handler.on_created(FileCreatedEvent(str(txt_file)))

    assert txt_file.exists()  # untouched
    assert len(engine.db.list_jobs()) == 0


def test_directory_event_ignored(engine, handler, dropbox_dirs):
    dropbox, _, _ = dropbox_dirs
    from watchdog.events import DirCreatedEvent

    handler.on_created(DirCreatedEvent(str(dropbox / "subdir")))
    assert len(engine.db.list_jobs()) == 0


# ---------------------------------------------------------------------------
# Integration test — full watchdog observer
# ---------------------------------------------------------------------------


def test_watchdog_picks_up_file(engine, tmp_path):
    dropbox_dir = tmp_path / "watch"
    dropbox = JobDropbox(engine, dropbox_dir).start()
    try:
        spec_file = dropbox_dir / "job.yml"
        spec_file.write_text(yaml.dump(VALID_SPEC))

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if (dropbox_dir / "submitted" / "job.yml").exists():
                break
            time.sleep(0.1)
        else:
            pytest.fail("Dropbox did not process file within 5 seconds")

        assert len(engine.db.list_jobs()) == 1
    finally:
        dropbox.stop()

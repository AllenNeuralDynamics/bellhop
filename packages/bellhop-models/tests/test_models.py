from pathlib import Path
import textwrap

import pytest
import yaml
from pydantic import ValidationError
from upath import UPath

from bellhop_models.specifications import (
    DeleteDataParams,
    DeleteDataTask,
    JobSpecification,
    HTTPRequestParams,
    HTTPRequestTask,
    RunSubprocessParams,
    SubprocessTask,
    SendMessageParams,
    SendMessageTask,
    TransferDataListParams,
    TransferDataParams,
    TransferDataTask,
)
from bellhop_models.database import Job


# ---------------------------------------------------------------------------
# Constructing Jobs in code
# ---------------------------------------------------------------------------


def _build_full_job() -> JobSpecification:
    return JobSpecification(
        name="My Pipeline",
        tasks=[
            SubprocessTask(
                name="Run script",
                parameters=RunSubprocessParams(program="python", command=["script.py"]),
            ),
            TransferDataTask(
                name="Copy single file",
                parameters=TransferDataParams(source="/tmp/result", destination="/archive"),
            ),
            TransferDataTask(
                name="Copy file list",
                parameters=TransferDataListParams(
                    source=["/tmp/a.txt", "/tmp/b.txt"],
                    destination="/archive",
                ),
            ),
            DeleteDataTask(
                name="Clean up",
                parameters=DeleteDataParams(source="/tmp/result"),
            ),
            SendMessageTask(
                name="Notify team",
                parameters=SendMessageParams(
                    recipient="team@example.com",
                    subject="Done",
                    body="Pipeline complete.",
                ),
            ),
            HTTPRequestTask(
                name="Trigger downstream",
                parameters=HTTPRequestParams(method="POST", url="http://example.com/trigger"),
            ),
        ],
    )


def test_build_job_in_code():
    """Each concrete task type can be constructed directly with typed parameters."""
    job = _build_full_job()

    assert len(job.tasks) == 6
    assert isinstance(job.tasks[0], SubprocessTask)
    assert job.tasks[0].parameters.program == "python"
    assert isinstance(job.tasks[1].parameters, TransferDataParams)
    assert isinstance(job.tasks[2].parameters, TransferDataListParams)


def test_job_serialization():
    """Serialized form includes task_type and all parameter fields."""

    def p(s: str) -> str:
        return str(UPath(s))  # normalise paths to the current platform

    job = _build_full_job()
    data = job.model_dump(mode="json", exclude={"scheduled_execution"})

    assert data == {
        "name": "My Pipeline",
        "description": None,
        "custom_fields": {},
        "tasks": [
            {
                "name": "Run script",
                "description": None,
                "task_type": "Subprocess",
                "parameters": {"program": "python", "command": ["script.py"]},
            },
            {
                "name": "Copy single file",
                "description": None,
                "task_type": "Move Data",
                "parameters": {"source": p("/tmp/result"), "destination": p("/archive"), "options": {}},
            },
            {
                "name": "Copy file list",
                "description": None,
                "task_type": "Move Data",
                "parameters": {
                    "source": [p("/tmp/a.txt"), p("/tmp/b.txt")],
                    "destination": p("/archive"),
                    "options": {},
                    "source_base_dir": None,
                    "preserve_structure": True,
                    "parallel": False,
                },
            },
            {
                "name": "Clean up",
                "description": None,
                "task_type": "Delete Data",
                "parameters": {"source": p("/tmp/result")},
            },
            {
                "name": "Notify team",
                "description": None,
                "task_type": "Send Message",
                "parameters": {
                    "recipient": "team@example.com",
                    "subject": "Done",
                    "body": "Pipeline complete.",
                },
            },
            {
                "name": "Trigger downstream",
                "description": None,
                "task_type": "HTTP Request",
                "parameters": {
                    "url": "http://example.com/trigger",
                    "method": "POST",
                    "headers": {},
                    "data": None,
                },
            },
        ],
    }


# ---------------------------------------------------------------------------
# Deserializing jobs from YAML
# ---------------------------------------------------------------------------


job_YAML = textwrap.dedent("""\
    name: My Pipeline
    tasks:
      - name: Run script
        task_type: Subprocess
        parameters:
          program: python
          command: [script.py, --verbose]
      - name: Copy results
        task_type: Move Data
        parameters:
          source: /tmp/results
          destination: /archive
      - name: Notify service
        task_type: HTTP Request
        parameters:
          method: POST
          url: http://example.com/notify
""")


def test_deserialize_job_from_yaml():
    """task_type in the YAML drives which concrete class is instantiated."""
    data = yaml.safe_load(job_YAML)
    job = JobSpecification.model_validate(data)

    assert len(job.tasks) == 3
    assert isinstance(job.tasks[0], SubprocessTask)
    assert job.tasks[0].parameters.program == "python"
    assert job.tasks[0].parameters.command == ["script.py", "--verbose"]

    assert isinstance(job.tasks[1], TransferDataTask)
    assert isinstance(job.tasks[1].parameters, TransferDataParams)

    assert isinstance(job.tasks[2], HTTPRequestTask)
    assert job.tasks[2].parameters.method == "POST"


def test_round_trip():
    """A job built in code serializes and deserializes back identically."""
    original = JobSpecification(
        name="Round Trip",
        tasks=[
            SubprocessTask(
                name="Run script",
                parameters=RunSubprocessParams(program="python", command=["script.py"]),
            ),
            HTTPRequestTask(
                name="Notify",
                parameters=HTTPRequestParams(url="http://example.com/done"),
            ),
        ],
    )
    data = original.model_dump(mode="json")
    restored = JobSpecification.model_validate(data)
    assert restored == original


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_bad_params_raises():
    """Missing required fields in parameters raises ValidationError."""
    with pytest.raises(ValidationError):
        SubprocessTask(name="bad", parameters={"nope": "nope"})


def test_wrong_param_type_raises():
    with pytest.raises(ValidationError):
        TransferDataTask(
            name="bad",
            parameters=RunSubprocessParams(program="python", command=["script.py"]),
        )


def test_unknown_task_type_in_yaml_raises():
    """An unrecognised task_type in YAML raises ValidationError."""
    data = yaml.safe_load(
        textwrap.dedent("""\
        name: Bad
        tasks:
          - name: x
            task_type: Unknown Type
            parameters: {}
    """)
    )
    with pytest.raises(ValidationError):
        JobSpecification.model_validate(data)


## Data transfer models, with multiple param types

test_cases = [
    {
        "input": TransferDataListParams(
            source=[Path("C:/data/file1.txt"), Path("C:/data/dir1")],
            destination=Path("D:/destination"),
        ),
        "expected": [
            TransferDataParams(source=Path("C:/data/file1.txt"), destination=Path("D:/destination"), options={}),
            TransferDataParams(source=Path("C:/data/dir1"), destination=Path("D:/destination"), options={}),
        ],
    },
    {
        "input": TransferDataListParams(
            source=[Path("C:/data/file1.txt"), Path("C:/data/dir1/file2.txt")],
            destination=Path("D:/destination"),
            source_base_dir=Path("C:/data"),
            preserve_structure=True,
        ),
        "expected": [
            TransferDataParams(source=Path("C:/data/file1.txt"), destination=Path("D:/destination/file1.txt")),
            TransferDataParams(
                source=Path("C:/data/dir1/file2.txt"), destination=Path("D:/destination/dir1/file2.txt")
            ),
        ],
    },
    {
        "input": TransferDataListParams(
            source=[Path("C:/data/file1.txt"), Path("C:/data/dir1")],
            destination=Path("D:/destination"),
            source_base_dir=Path("C:/data"),
            preserve_structure=False,
        ),
        "expected": [
            TransferDataParams(source=Path("C:/data/file1.txt"), destination=Path("D:/destination"), options={}),
            TransferDataParams(source=Path("C:/data/dir1"), destination=Path("D:/destination"), options={}),
        ],
    },
]


@pytest.mark.parametrize("input, expected", [(case["input"], case["expected"]) for case in test_cases])
def test_transfer_data_params_model(input: TransferDataListParams, expected: list[TransferDataParams]):
    transfers = input.construct_individual_transfers()
    assert transfers == expected


def test_spec_to_internal():
    job_spec = _build_full_job()

    job = Job.from_specification(job_spec)

    assert isinstance(job, Job)
    new = JobSpecification(**job.model_dump())
    assert new == job_spec

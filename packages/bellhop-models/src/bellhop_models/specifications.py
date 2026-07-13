"""JobSpecification and TaskSpecification models,
including specific task/parameter models for each task type.

These are used to submit data to bellhop, and when ingested will be
converted into the database models in models_db.py.

Examples
--------
>>> from bellhop_models.specifications import JobSpecification, TransferDataTask, TransferDataParams
>>> job = JobSpecification(
...     name="My Pipeline",
...     tasks=[
...         TransferDataTask(
...             name="Copy file",
...             parameters=TransferDataParams(source="/tmp/result", destination="/archive"),
...         )
...     ]
... )
"""

from datetime import datetime, time
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer
from upath import UPath as _UPath


## Type coercion util


def coerce_upath(value) -> _UPath:
    """Coerce a value into a UPath instance or raise ValueError. Used for pydantic validation."""
    try:
        return _UPath(value)
    except Exception as e:
        raise ValueError(f"Cannot convert to UPath: {value}") from e


UPath = Annotated[_UPath, BeforeValidator(coerce_upath), PlainSerializer(str, return_type=str)]

##

TaskTypes = Literal[
    "Move Data",
    "Delete Data",
    "Send Message",
    "Subprocess",
    "HTTP Request",
]


class TaskSpecification[ParamsT](BaseModel):
    name: str
    description: Optional[str] = None
    task_type: TaskTypes
    parameters: ParamsT


## Models for each task type


###  Move Data


class TransferDataParams(BaseModel, arbitrary_types_allowed=True):
    source: UPath
    destination: UPath
    options: dict = {}  # Additional storage-specific options


class TransferDataListParams(BaseModel, arbitrary_types_allowed=True):
    source: list[UPath]
    destination: UPath
    options: dict = {}  # Additional storage-specific options
    source_base_dir: Optional[UPath] = None  # Optional base dir common to all sources
    preserve_structure: bool = True  # If source_base_dir, will preserve relative paths
    parallel: bool = False  # Whether to perform transfers in parallel

    def construct_individual_transfers(self) -> list[TransferDataParams]:
        """
        Generate a list of TransferDataParams for each source

        Examples:
        >>> params = TransferDataListParams(
        ...     source=[UPath("C:/data/file1.txt"), UPath("C:/data/dir1")],
        ...     destination=UPath("D:/backup"),
        ...     )
        >>> params.construct_individual_transfers()
        [TransferDataParams(source=WindowsUPath('C:/data/file1.txt'), destination=WindowsUPath('D:/backup'), options={}), TransferDataParams(source=WindowsUPath('C:/data/dir1'), destination=WindowsUPath('D:/backup'), options={})]

        """
        individual_transfers: list[TransferDataParams] = []
        for src in self.source:
            src = self.source_base_dir / src if self.source_base_dir else src
            if self.preserve_structure and self.source_base_dir:
                relative_path = src.relative_to(self.source_base_dir)
                dest = self.destination / relative_path
            else:
                dest = self.destination

            individual_transfers.append(TransferDataParams(source=src, destination=dest, options=self.options))

        return individual_transfers


class TransferDataTask(TaskSpecification[TransferDataParams | TransferDataListParams]):
    task_type: Literal["Move Data"] = "Move Data"
    parameters: TransferDataParams | TransferDataListParams


### Delete Data


class DeleteDataParams(BaseModel, arbitrary_types_allowed=True):
    source: UPath


class DeleteDataTask(TaskSpecification[DeleteDataParams]):
    task_type: Literal["Delete Data"] = "Delete Data"
    parameters: DeleteDataParams


### Run subprocess


class RunSubprocessParams(BaseModel):
    program: str
    command: list[str]


class SubprocessTask(TaskSpecification[RunSubprocessParams]):
    task_type: Literal["Subprocess"] = "Subprocess"
    parameters: RunSubprocessParams


### Send message


class SendMessageParams(BaseModel):
    recipient: str
    subject: str
    body: str


class SendMessageTask(TaskSpecification[SendMessageParams]):
    task_type: Literal["Send Message"] = "Send Message"
    parameters: SendMessageParams


### HTTP Request


class HTTPRequestParams(BaseModel):
    url: str
    method: Literal["GET", "POST", "PUT", "DELETE"] = "GET"
    headers: dict = {}
    data: Optional[dict] = None


class HTTPRequestTask(TaskSpecification[HTTPRequestParams]):
    task_type: Literal["HTTP Request"] = "HTTP Request"
    parameters: HTTPRequestParams


### AnyTask Annotation and JobSpecification


AnyTask = Annotated[
    SubprocessTask | TransferDataTask | DeleteDataTask | SendMessageTask | HTTPRequestTask,
    Field(discriminator="task_type"),
]


class JobSpecification(BaseModel):
    name: str
    description: Optional[str] = None
    custom_fields: dict = {}
    scheduled_execution: datetime | time = Field(default_factory=datetime.now)
    tasks: list[AnyTask]

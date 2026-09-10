"""Job, Task, and TaskExecution models used for internal tracking"""

import uuid
from datetime import datetime, time
from typing import Literal, Self

from pydantic import BaseModel, Field

from bellhop_models.specifications import JobSpecification, TaskSpecification

TaskStates = Literal["Not Started", "In Progress", "Completed", "Errored"]


## Internal execution tracking models


class TaskExecution(BaseModel):
    """Tracks a single execution of a Task."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task: "Task"
    success: bool | None = None  # None while in-progress
    message: str | None = None
    time_started: datetime
    time_ended: datetime | None = None  # None while in-progress
    logs: str = ""


class Task[ParamsT](BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    state: TaskStates = "Not Started"

    name: str
    description: str | None = None
    task_type: str
    parameters: ParamsT

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_specification(cls, specification: TaskSpecification) -> Self:
        return cls[type(specification.parameters)](**specification.model_dump())


class Job(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    state: TaskStates = "Not Started"

    name: str
    description: str | None = None
    custom_fields: dict = {}

    tasks: list[Task]
    time_submitted: datetime = Field(default_factory=datetime.now)  # when the job was created
    time_scheduled: datetime = Field(default_factory=datetime.now)  # originally requested execution time
    next_execution_time: datetime = Field(default_factory=datetime.now)  # execution time currently queued
    history: list[TaskExecution] = []

    next_task: int | None = 0

    @classmethod
    def from_specification(cls, specification: JobSpecification) -> Self:
        now = datetime.now()
        time_scheduled = specification.time_scheduled
        if time_scheduled is None or isinstance(time_scheduled, time):
            time_scheduled = now
        return cls(
            tasks=[Task.from_specification(t) for t in specification.tasks],
            time_submitted=now,
            time_scheduled=time_scheduled,
            next_execution_time=time_scheduled,
            **specification.model_dump(exclude={"tasks", "time_scheduled"}, exclude_none=True),
        )

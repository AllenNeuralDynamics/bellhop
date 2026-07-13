"""Job, Task, and TaskExecution models used for internal tracking"""

from datetime import datetime
from typing import Literal, Optional, Self
import uuid

from pydantic import BaseModel, Field

from bellhop_models.specifications import TaskSpecification, JobSpecification


TaskStates = Literal["Not Started", "In Progress", "Completed", "Errored"]


## Internal execution tracking models


class TaskExecution(BaseModel):
    """Tracks a single execution of a Task."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task: "Task"
    success: bool
    message: Optional[str] = None
    time_started: datetime
    time_ended: datetime
    logs: str


class Task[ParamsT](BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    state: TaskStates = "Not Started"

    name: str
    description: Optional[str] = None
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
    description: Optional[str] = None
    custom_fields: dict = {}

    tasks: list[Task]
    scheduled_execution: datetime
    history: list[TaskExecution] = []

    next_task: int = 0

    @classmethod
    def from_specification(cls, specification: JobSpecification) -> Self:
        return cls(
            tasks=[Task.from_specification(t) for t in specification.tasks],
            **specification.model_dump(exclude={"tasks"}),
        )

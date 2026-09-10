import uuid
from datetime import datetime
from typing import Literal

from bellhop_models.database import Job, Task, TaskExecution, TaskStates
from bellhop_models.specifications import AnyTaskAdapter
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, and_, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class JobSql(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(default="Not Started")
    name: Mapped[str]
    description: Mapped[str | None]
    next_task: Mapped[int | None] = mapped_column(default=0)
    time_submitted: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    time_scheduled: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_execution_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)

    tasks: Mapped[list["TaskSql"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    history: Mapped[list["TaskExecutionSql"]] = relationship(
        "TaskExecutionSql",
        secondary="tasks",
        primaryjoin="JobSql.id == TaskSql.job_id",
        secondaryjoin="TaskSql.id == TaskExecutionSql.task_id",
        viewonly=True,
        overlaps="executions,job,tasks",
    )

    def to_model(self) -> Job:
        return Job(
            id=self.id,
            state=self.state,
            name=self.name,
            description=self.description,
            next_task=self.next_task,
            time_submitted=self.time_submitted,
            time_scheduled=self.time_scheduled,
            next_execution_time=self.next_execution_time,
            custom_fields=self.custom_fields,
            tasks=[t.to_model() for t in self.tasks],
            history=[e.to_model() for e in self.history],
        )

    @classmethod
    def from_model(cls, job: Job) -> "JobSql":
        row = cls(
            id=job.id,
            state=job.state,
            name=job.name,
            description=job.description,
            next_task=job.next_task,
            time_submitted=job.time_submitted,
            time_scheduled=job.time_scheduled,
            next_execution_time=job.next_execution_time,
            custom_fields=job.custom_fields,
        )
        row.tasks = [TaskSql.from_model(t, job.id) for t in job.tasks]
        return row


class TaskSql(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(default="Not Started")
    name: Mapped[str]
    description: Mapped[str | None]
    task_type: Mapped[str]
    parameters: Mapped[dict] = mapped_column(JSON)

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"))
    job: Mapped["JobSql"] = relationship(back_populates="tasks")
    executions: Mapped[list["TaskExecutionSql"]] = relationship(back_populates="task", cascade="all, delete-orphan")

    def to_model(self) -> Task:
        spec = AnyTaskAdapter.validate_python(
            {"task_type": self.task_type, "name": self.name, "parameters": self.parameters}
        )
        return Task(
            id=self.id,
            state=self.state,
            name=self.name,
            description=self.description,
            task_type=self.task_type,
            parameters=spec.parameters,
        )

    @classmethod
    def from_model(cls, task: Task, job_id: uuid.UUID) -> "TaskSql":
        params = task.parameters
        if isinstance(params, BaseModel):
            params = params.model_dump(mode="json")
        return cls(
            id=task.id,
            state=task.state,
            name=task.name,
            description=task.description,
            task_type=task.task_type,
            parameters=params,
            job_id=job_id,
        )


class TaskExecutionSql(Base):
    __tablename__ = "task_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"))
    success: Mapped[bool | None]
    message: Mapped[str | None]
    time_started: Mapped[datetime]
    time_ended: Mapped[datetime | None]
    logs: Mapped[str]

    task: Mapped["TaskSql"] = relationship(back_populates="executions")

    def to_model(self) -> TaskExecution:
        return TaskExecution(
            id=self.id,
            task=self.task.to_model(),
            success=self.success,
            message=self.message,
            time_started=self.time_started,
            time_ended=self.time_ended,
            logs=self.logs,
        )

    @classmethod
    def from_model(cls, execution: TaskExecution) -> "TaskExecutionSql":
        return cls(
            id=execution.id,
            task_id=execution.task.id,
            success=execution.success,
            message=execution.message,
            time_started=execution.time_started,
            time_ended=execution.time_ended,
            logs=execution.logs,
        )


DATABASE_FILE = "bellhop_jobs.db"


class Database:
    def __init__(self, db_file: str = DATABASE_FILE):
        self._db_file = db_file
        url = "sqlite:///:memory:" if db_file == ":memory:" else f"sqlite:///{db_file}"
        _engine = create_engine(url)
        Base.metadata.create_all(_engine)
        self._Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    def create_job(self, job: Job) -> Job:
        with self._Session() as session:
            row = JobSql.from_model(job)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_model()

    def get_job(self, job_id: uuid.UUID) -> Job | None:
        with self._Session() as session:
            row = session.get(JobSql, job_id)
            return row.to_model() if row else None

    def list_jobs(self) -> list[Job]:
        return self.query_jobs()

    def query_jobs(
        self,
        *,
        name_contains: str | None = None,
        description_contains: str | None = None,
        state_list: list[TaskStates] | None = None,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        order_by: tuple[tuple[str, Literal["asc", "desc"]]] = (("time_submitted", "desc"),),
    ) -> list[Job]:
        if scheduled_from is not None and scheduled_to is not None and scheduled_from > scheduled_to:
            raise ValueError("scheduled_from must be less than or equal to scheduled_to")

        filters = []

        if name_contains and name_contains.strip():
            filters.append(JobSql.name.ilike(f"%{name_contains.strip()}%"))

        if description_contains and description_contains.strip():
            filters.append(JobSql.description.ilike(f"%{description_contains.strip()}%"))

        if scheduled_from is not None:
            filters.append(JobSql.next_execution_time >= scheduled_from)

        if scheduled_to is not None:
            filters.append(JobSql.next_execution_time <= scheduled_to)

        if state_list is not None:
            filters.append(JobSql.state.in_(state_list))

        statement = select(JobSql)
        if filters:
            statement = statement.where(and_(*filters))
        if order_by:
            for col, direction in order_by:
                statement = statement.order_by(
                    getattr(JobSql, col).desc() if direction == "desc" else getattr(JobSql, col)
                )

        with self._Session() as session:
            rows = session.execute(statement).scalars().all()
            return [r.to_model() for r in rows]

    def update_job(self, job: Job) -> Job:
        with self._Session() as session:
            row = session.get(JobSql, job.id)
            if row is None:
                raise KeyError(f"Job {job.id} not found")
            row.state = job.state
            row.name = job.name
            row.description = job.description
            row.next_task = job.next_task
            row.next_execution_time = job.next_execution_time
            row.custom_fields = job.custom_fields
            session.commit()
            session.refresh(row)
            return row.to_model()

    def delete_job(self, job_id: uuid.UUID) -> None:
        with self._Session() as session:
            row = session.get(JobSql, job_id)
            if row is None:
                raise KeyError(f"Job {job_id} not found")
            session.delete(row)
            session.commit()

    def get_task(self, task_id: uuid.UUID) -> Task | None:
        with self._Session() as session:
            row = session.get(TaskSql, task_id)
            return row.to_model() if row else None

    def update_task(self, task: Task) -> Task:
        with self._Session() as session:
            row = session.get(TaskSql, task.id)
            if row is None:
                raise KeyError(f"Task {task.id} not found")
            row.state = task.state
            row.name = task.name
            row.description = task.description
            row.task_type = task.task_type
            params = task.parameters
            if isinstance(params, BaseModel):
                params = params.model_dump(mode="json")
            row.parameters = params
            session.commit()
            session.refresh(row)
            return row.to_model()

    def add_execution(self, execution: TaskExecution) -> TaskExecution:
        with self._Session() as session:
            row = TaskExecutionSql.from_model(execution)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_model()

    def get_execution(self, execution_id: uuid.UUID) -> TaskExecution | None:
        with self._Session() as session:
            row = session.get(TaskExecutionSql, execution_id)
            return row.to_model() if row else None

    def update_execution(self, execution: TaskExecution) -> TaskExecution:
        with self._Session() as session:
            row = session.get(TaskExecutionSql, execution.id)
            if row is None:
                raise KeyError(f"TaskExecution {execution.id} not found")
            row.success = execution.success
            row.message = execution.message
            row.time_ended = execution.time_ended
            row.logs = execution.logs
            session.commit()
            session.refresh(row)
            return row.to_model()

    def _update_execution_logs(self, execution_id: uuid.UUID, logs: str) -> None:
        with self._Session() as session:
            row = session.get(TaskExecutionSql, execution_id)
            if row is not None:
                row.logs = logs
                session.commit()

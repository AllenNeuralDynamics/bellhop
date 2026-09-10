import asyncio
import uuid

import reflex as rx
import yaml
from bellhop_client.client import AsyncBellhopClient
from bellhop_models.database import Job, Task, TaskExecution
from bellhop_models.specifications import JobSpecification

api_client = AsyncBellhopClient()

JOB_POLL_INTERVAL_SECONDS = 5


class State(rx.State):
    api_environment_info: dict[str, str] = {}
    jobs: list[Job] = []
    selected_job: Job | None = None
    selected_task_id: str = ""
    selected_execution_id: str = ""

    @rx.var
    def selected_job_tasks(self) -> list[Task]:
        return self.selected_job.tasks if self.selected_job is not None else []

    @rx.var
    def selected_task(self) -> Task | None:
        return next((task for task in self.selected_job_tasks if str(task.id) == self.selected_task_id), None)

    @rx.var
    def selected_task_yaml(self) -> str:
        if self.selected_task is None:
            return ""
        return yaml.dump(self.selected_task.model_dump(mode="json"), sort_keys=False)

    def set_selected_task_id(self, task_id: str):
        self.selected_task_id = task_id
        self.selected_execution_id = next(
            (
                str(execution.id)
                for execution in reversed(self.selected_job.history if self.selected_job else [])
                if str(execution.task.id) == task_id
            ),
            "",
        )

    def set_selected_execution_id(self, execution_id: str | list[str]):
        self.selected_execution_id = execution_id if isinstance(execution_id, str) else next(iter(execution_id), "")

    @rx.var
    def selected_task_executions(self) -> list[TaskExecution]:
        if self.selected_job is None:
            return []
        return [execution for execution in self.selected_job.history if str(execution.task.id) == self.selected_task_id]

    @rx.var
    def selected_task_executions_most_recent_first(self) -> list[TaskExecution]:
        return list(reversed(self.selected_task_executions))

    ## API calls

    async def _refresh_jobs(self) -> None:
        async with self:
            selected_job_id = self.selected_job.id if self.selected_job is not None else None
        jobs = await api_client.list_jobs()
        # keep the detail view in sync with the list without resetting the current selection
        selected_job = await api_client.get_job(selected_job_id) if selected_job_id is not None else None
        async with self:
            self.jobs = jobs
            if selected_job_id is not None:
                self.selected_job = selected_job

    @rx.event(background=True)
    async def get_environment(self):
        environment = await api_client.get_environment()
        async with self:
            self.api_environment_info = environment

    @rx.event(background=True)
    async def fetch_jobs(self):
        await self._refresh_jobs()

    @rx.event(background=True)
    async def auto_refresh_jobs(self):
        while True:
            await asyncio.sleep(JOB_POLL_INTERVAL_SECONDS)
            await self._refresh_jobs()

    @rx.event(background=True)
    async def submit_job(self, spec: dict):
        job_spec = JobSpecification.model_validate(spec)
        await api_client.submit_job(job_spec)
        await self._refresh_jobs()

    @rx.event(background=True)
    async def get_job(self, job_id: str):
        job = await api_client.get_job(uuid.UUID(job_id))
        async with self:
            self.selected_job = job
            self.selected_task_id = ""
            self.selected_execution_id = ""

    @rx.event(background=True)
    async def update_job(self, job: dict):
        job_id = uuid.UUID(job["id"])
        job_obj = Job.model_validate(job)
        await api_client.update_job(job_id, job_obj)
        await self._refresh_jobs()

    @rx.event(background=True)
    async def abort_job(self, job_id: str):
        await api_client.abort_job(uuid.UUID(job_id))
        await self._refresh_jobs()

    @rx.event(background=True)
    async def execute_now(self, job_id: str):
        print(job_id)
        await api_client.execute_now(uuid.UUID(job_id))
        await self._refresh_jobs()

    @rx.event(background=True)
    async def retry_job(self, job_id: str):
        await api_client.retry_job(uuid.UUID(job_id))
        await self._refresh_jobs()

    # def get_execution(self, execution_id: str):
    #     self.selected_execution = client.get_execution(uuid.UUID(execution_id)).model_dump(mode="json")

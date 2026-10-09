import asyncio
import logging
import uuid

import reflex as rx
import yaml
from bellhop_models.database import Job, JobSummary, Task, TaskExecution
from bellhop_models.specifications import JobSpecification

from bellhop_ui.bellhop_ui import app
from bellhop_ui.state import State, TabVisibilityMixin


class JobTableState(TabVisibilityMixin, State):
    """Job-list page state: the jobs table, selection, polling and tab visibility.

    Inherits the shared base ``State`` so connection/settings vars are shared with
    the rest of the app; the polling here is specific to the job-list page.
    """

    jobs: list[JobSummary] = []
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

    @rx.var
    def selected_task_executions(self) -> list[TaskExecution]:
        if self.selected_job is None:
            return []
        return [execution for execution in self.selected_job.history if str(execution.task.id) == self.selected_task_id]

    @rx.var
    def selected_task_executions_most_recent_first(self) -> list[TaskExecution]:
        return list(reversed(self.selected_task_executions))

    @rx.event
    def set_selected_task_id(self, task_id: str) -> None:
        self.selected_task_id = task_id
        self.selected_execution_id = next(
            (
                str(execution.id)
                for execution in reversed(self.selected_job.history if self.selected_job else [])
                if str(execution.task.id) == task_id
            ),
            "",
        )

    @rx.event
    def set_selected_execution_id(self, execution_id: str | list[str]) -> None:
        self.selected_execution_id = execution_id if isinstance(execution_id, str) else next(iter(execution_id), "")

    @rx.event
    def on_visible(self):
        # Tab came back; catch up immediately instead of waiting for the next poll tick.
        yield JobTableState.fetch_jobs

    async def _refresh_jobs(self) -> None:
        async with self:
            if not self.connected:
                return
            client = self.api_client
            selected_job_id = self.selected_job.id if self.selected_job is not None else None

        # Let failures propagate so the calling background task can yield check_connection.
        jobs = await client.list_jobs()
        selected_job = await client.get_job(selected_job_id) if selected_job_id is not None else None

        async with self:
            self.jobs = jobs
            if selected_job_id is not None:
                self.selected_job = selected_job

    @rx.event(background=True)
    async def init_page(self):
        # Connect first, then load everything at once, so jobs appear immediately on a
        # cold load instead of waiting for the next poll tick.
        async with self:
            client = self.api_client

        try:
            await client.health_check()
        except Exception:
            logging.exception("failed to connect")
            async with self:
                self.connected = False
            return

        async with self:
            self.connected = True

        yield State.get_environment
        yield JobTableState.fetch_jobs

    @rx.event(background=True)
    async def fetch_jobs(self):
        try:
            await self._refresh_jobs()
        except Exception:
            logging.exception("failed to refresh jobs")
            yield State.check_connection

    @rx.event(background=True)
    async def auto_refresh_jobs(self):
        while True:
            async with self:
                interval = self.api_jobs_poll_interval_seconds

            await asyncio.sleep(interval)

            if self.router.session.client_token not in app.event_namespace.token_to_sid:
                print("WebSocket connection closed or user navigated away. Stopping background task.")
                break

            async with self:
                connected = self.connected
                visible = self.tab_visible

            if not visible:
                # Tab is hidden; pause polling until it becomes visible again.
                continue

            if not connected:
                # Re-verify connection; skip the refresh until we're back.
                yield State.check_connection
                continue

            try:
                await self._refresh_jobs()
            except Exception:
                logging.exception("failed to refresh jobs")
                yield State.check_connection

    @rx.event(background=True)
    async def submit_job(self, spec: dict):
        async with self:
            if not self.connected:
                return
            client = self.api_client

        try:
            job_spec = JobSpecification.model_validate(spec)
            await client.submit_job(job_spec)
            await self._refresh_jobs()
        except Exception:
            yield State.check_connection

    @rx.event(background=True)
    async def get_job(self, job_id: str):
        async with self:
            if not self.connected:
                return
            client = self.api_client

        try:
            job = await client.get_job(uuid.UUID(job_id))
            async with self:
                self.selected_job = job
                self.selected_task_id = ""
                self.selected_execution_id = ""
        except Exception:
            yield State.check_connection

    @rx.event(background=True)
    async def update_job(self, job: dict):
        async with self:
            if not self.connected:
                return
            client = self.api_client

        try:
            job_id = uuid.UUID(job["id"])
            job_obj = Job.model_validate(job)
            await client.update_job(job_id, job_obj)
            await self._refresh_jobs()
        except Exception:
            yield State.check_connection

    @rx.event(background=True)
    async def abort_job(self, job_id: str):
        async with self:
            if not self.connected:
                return
            client = self.api_client

        try:
            await client.abort_job(uuid.UUID(job_id))
            await self._refresh_jobs()
        except Exception:
            yield State.check_connection

    @rx.event(background=True)
    async def execute_now(self, job_id: str):
        async with self:
            if not self.connected:
                return
            client = self.api_client

        try:
            await client.execute_now(uuid.UUID(job_id))
            await self._refresh_jobs()
        except Exception:
            yield State.check_connection

    @rx.event(background=True)
    async def retry_job(self, job_id: str):
        async with self:
            if not self.connected:
                return
            client = self.api_client

        try:
            await client.retry_job(uuid.UUID(job_id))
            await self._refresh_jobs()
        except Exception:
            yield State.check_connection

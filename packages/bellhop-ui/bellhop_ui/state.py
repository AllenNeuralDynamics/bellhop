import asyncio
import logging
import uuid

import reflex as rx
import yaml
from bellhop_client.client import AsyncBellhopClient
from bellhop_models.database import Job, JobSummary, Task, TaskExecution
from bellhop_models.specifications import JobSpecification


class ClientRegistry:
    """Out-of-state registry mapping session IDs to AsyncBellhopClient instances.
    Reflex can't keep non-pickleable objects in state, so this way we can have separate
    client instances per UI session."""

    _clients: dict[str, AsyncBellhopClient] = {}

    @classmethod
    def get_client(cls, session_id: str, base_url: str) -> AsyncBellhopClient:
        # Create a new client if one doesn't exist for this session
        if session_id not in cls._clients:
            cls._clients[session_id] = AsyncBellhopClient(base_url=base_url)
        return cls._clients[session_id]

    @classmethod
    def update_client(cls, session_id: str, base_url: str) -> AsyncBellhopClient:
        """Re-instantiates client when base_url or auth changes."""
        old_client = cls._clients.get(session_id)
        if old_client and hasattr(old_client, "close"):
            asyncio.create_task(old_client.close())

        new_client = AsyncBellhopClient(base_url=base_url)
        cls._clients[session_id] = new_client
        return new_client

    @classmethod
    def remove_client(cls, session_id: str):
        if session_id in cls._clients:
            del cls._clients[session_id]


class State(rx.State):
    api_jobs_poll_interval_seconds: int = 5
    api_base_url: str = "http://localhost:8312"
    connected: bool = False
    api_environment_info: dict[str, str] = {}
    jobs: list[JobSummary] = []
    selected_job: Job | None = None
    selected_task_id: str = ""
    selected_execution_id: str = ""
    settings_dialog_open: bool = False

    @property
    def api_client(self) -> AsyncBellhopClient:
        """Helper to safely access the per-session client in any event or background task."""
        return ClientRegistry.get_client(self.router.session.session_id, self.api_base_url)

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

    @rx.event
    def clear_state(self) -> None:
        self.jobs = []
        self.selected_job = None
        self.selected_task_id = ""
        self.selected_execution_id = ""
        self.api_environment_info = {}

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

    @rx.var
    def selected_task_executions(self) -> list[TaskExecution]:
        if self.selected_job is None:
            return []
        return [execution for execution in self.selected_job.history if str(execution.task.id) == self.selected_task_id]

    @rx.var
    def selected_task_executions_most_recent_first(self) -> list[TaskExecution]:
        return list(reversed(self.selected_task_executions))

    @rx.event
    def set_settings_dialog_open(self, open: bool) -> None:
        self.settings_dialog_open = open

    @rx.event
    async def change_settings(self, new_values: dict):
        if (new_url := new_values.get("api_base_url")) and new_url != self.api_base_url:
            self.api_base_url = new_url
            ClientRegistry.update_client(self.router.session.session_id, self.api_base_url)
            self.clear_state()

        if new_interval := new_values.get("api_jobs_poll_interval_seconds"):
            self.api_jobs_poll_interval_seconds = int(new_interval)

        # Trigger connection check first; if successful, check_connection will trigger environment & jobs fetch
        yield State.check_connection

    ## API calls

    @rx.event(background=True)
    async def check_connection(self) -> None:
        try:
            async with self:
                await self.api_client.health_check()

            async with self:
                self.connected = True

            # If connection succeeds, fetch environment info & job list immediately
            yield State.get_environment()
            yield State.fetch_jobs()

        except Exception:
            logging.exception("failed to connect")
            async with self:
                self.connected = False

    async def _refresh_jobs(self) -> None:
        async with self:
            if not self.connected:
                return
            client = self.api_client
            selected_job_id = self.selected_job.id if self.selected_job is not None else None

        try:
            jobs = await client.list_jobs()
            selected_job = await client.get_job(selected_job_id) if selected_job_id is not None else None

            async with self:
                self.jobs = jobs
                if selected_job_id is not None:
                    self.selected_job = selected_job
        except Exception:
            return State.check_connection

    @rx.event(background=True)
    async def get_environment(self):
        async with self:
            if not self.connected:
                return
            client = self.api_client

        try:
            environment = await client.get_environment()
            async with self:
                self.api_environment_info = environment
        except Exception:
            async with self:
                self.connected = False

    @rx.event(background=True)
    async def fetch_jobs(self):
        await self._refresh_jobs()

    @rx.event(background=True)
    async def auto_refresh_jobs(self):
        while True:
            await asyncio.sleep(self.api_jobs_poll_interval_seconds)

            # Re-verify connection status periodically
            yield State.check_connection

            async with self:
                if not self.connected:
                    continue
            await self._refresh_jobs()

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
            return State.check_connection

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
            return State.check_connection

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
            return State.check_connection

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
            return State.check_connection

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
            return State.check_connection

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
            return State.check_connection

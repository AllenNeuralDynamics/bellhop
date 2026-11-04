import asyncio
import logging
import uuid

import reflex as rx
import yaml
from bellhop_models import Job, Task, TaskExecution
from reflex_resizable_panels import resizable_panels as rzp

from bellhop_ui.bellhop_ui import app
from bellhop_ui.pages.shared import (
    pretty_resize_handle,
    state_badge,
)
from bellhop_ui.state import State, TabVisibilityMixin, api_call


class JobDetailState(TabVisibilityMixin, State):
    """Job-detail page state: the selected job, task, execution, and tab visibility.

    Inherits the shared base ``State`` so connection/settings vars are shared with
    the rest of the app; the polling here is specific to the job-list page.
    """

    # selected_job_id: str | None = None
    selected_job: Job | None = None
    selected_task_id: str = ""
    selected_execution_id: str = ""

    @rx.event
    def parse_query_params(self):
        # router.url.query_parameters returns a frozen Mapping[str, str]
        params = self.router.url.query_parameters
        job_id = params.get("job")
        if isinstance(job_id, str):
            yield JobDetailState.get_job(job_id)

    @rx.event
    def copy_job_id(self):
        if self.selected_job is not None:
            yield rx.set_clipboard(self.selected_job.id)
            yield rx.toast.success("Job ID copied to clipboard")

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
        yield JobDetailState.fetch_job

    async def _refresh_job(self) -> None:
        async with self:
            if not self.connected:
                return
            client = self.api_client
            selected_job_id = self.selected_job.id if self.selected_job is not None else None

        if selected_job_id is None:
            return

        # Let failures propagate so the calling background task can yield check_connection.
        selected_job = await client.get_job(selected_job_id)

        async with self:
            self.selected_job = selected_job

    @rx.event(background=True)
    async def fetch_job(self):
        try:
            await self._refresh_job()
        except Exception:
            logging.exception("failed to refresh job")
            yield State.check_connection

    @rx.event(background=True)
    async def auto_refresh_job(self):
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
                has_selection = self.selected_job is not None

            if not visible or not has_selection:
                # Nothing to refresh while hidden or with no job selected.
                continue

            if not connected:
                # Re-verify connection; skip the refresh until we're back.
                yield State.check_connection
                continue

            try:
                await self._refresh_job()
            except Exception:
                logging.exception("failed to refresh job")
                yield State.check_connection

    @rx.event(background=True)
    @api_call
    async def get_job(self, job_id: str):
        async with self:
            client = self.api_client
        job = await client.get_job(uuid.UUID(job_id))
        async with self:
            self.selected_job = job
            self.selected_task_id = ""
            self.selected_execution_id = ""

    @rx.event(background=True)
    @api_call
    async def update_job(self, job: dict):
        async with self:
            client = self.api_client
        job_id = uuid.UUID(job["id"])
        job_obj = Job.model_validate(job)
        await client.update_job(job_id, job_obj)
        await self._refresh_job()

    @rx.event(background=True)
    @api_call
    async def abort_job(self, job_id: str):
        async with self:
            client = self.api_client
        await client.abort_job(uuid.UUID(job_id))
        await self._refresh_job()

    @rx.event(background=True)
    @api_call
    async def execute_now(self, job_id: str):
        async with self:
            client = self.api_client
        await client.execute_now(uuid.UUID(job_id))
        await self._refresh_job()

    @rx.event(background=True)
    @api_call
    async def retry_job(self, job_id: str):
        async with self:
            client = self.api_client
        await client.retry_job(uuid.UUID(job_id))
        await self._refresh_job()


def execution_summary(execution: TaskExecution) -> rx.Component:
    return rx.hstack(
        rx.match(
            execution.success,
            (True, rx.badge("Success", color_scheme="green")),
            (False, rx.badge("Failed", color_scheme="red")),
            rx.badge("Running", color_scheme="blue"),
        ),
        rx.text(execution.time_started, size="1", color="gray"),
        rx.cond(
            execution.time_ended,
            rx.text("→ ", execution.time_ended, size="1", color="gray"),
            rx.fragment(),
        ),
        align="center",
        spacing="2",
    )


def execution_record(execution: TaskExecution) -> rx.Component:
    return rx.box(
        rx.cond(
            execution.message,
            rx.text(execution.message, size="1"),
            rx.fragment(),
        ),
        rx.cond(
            execution.logs,
            rx.scroll_area(
                rx.code_block(
                    execution.logs,
                    language="bash",
                    width="100%",
                ),
                max_height="200px",
                width="100%",
            ),
            rx.fragment(),
        ),
        padding_left="3",
        margin_top="2",
        width="100%",
    )


def execution_accordion_item(execution: TaskExecution) -> rx.Component:
    return rx.accordion.item(
        header=execution_summary(execution),
        content=execution_record(execution),
        value=execution.id.to(str),
    )


def task_pill(task: Task) -> rx.Component:
    is_selected = task.id == JobDetailState.selected_task_id
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(task.name, weight="bold", size="2"),
                rx.badge(task.task_type, variant="outline", size="1"),
                spacing="2",
                align="center",
            ),
            state_badge(task.state),
            spacing="1",
            align="start",
        ),
        on_click=JobDetailState.set_selected_task_id(task.id),
        cursor="pointer",
        outline=rx.cond(is_selected, "2px solid var(--accent-9)", "none"),
        min_width="160px",
    )


def job_detail_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.grid(
                rx.hstack(
                    rx.vstack(
                        rx.heading(JobDetailState.selected_job.name, size="4"),
                        rx.hstack(
                            rx.text(JobDetailState.selected_job.id, size="1"),
                            rx.button(
                                rx.icon("copy", size=15),
                                variant="ghost",
                                size="1",
                                on_click=JobDetailState.copy_job_id,
                            ),
                        ),
                    ),
                    rx.spacer(),
                    state_badge(JobDetailState.selected_job.state),
                    rx.spacer(),
                    align="center",
                ),
                rx.vstack(
                    rx.text(JobDetailState.selected_job.description, size="2"),
                    rx.hstack(
                        rx.text("Submitted: ", JobDetailState.selected_job.time_submitted, size="1", color="gray"),
                        rx.text(
                            "Originally scheduled: ", JobDetailState.selected_job.time_scheduled, size="1", color="gray"
                        ),
                        rx.text(
                            "Next execution: ", JobDetailState.selected_job.next_execution_time, size="1", color="gray"
                        ),
                        spacing="3",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.hstack(
                    rx.cond(
                        JobDetailState.selected_job.state == "Not Started",
                        rx.button(
                            "Execute Now",
                            on_click=JobDetailState.execute_now(JobDetailState.selected_job.id),
                            size="1",
                        ),
                        rx.fragment(),
                    ),
                    rx.button(
                        "Retry",
                        on_click=JobDetailState.retry_job(JobDetailState.selected_job.id),
                        size="1",
                        variant="soft",
                    ),
                    rx.button(
                        "Abort",
                        on_click=JobDetailState.abort_job(JobDetailState.selected_job.id),
                        size="1",
                        color_scheme="red",
                        variant="soft",
                    ),
                    spacing="1",
                    justify_self="end",
                ),
                columns="1fr 1fr auto",
                align="center",
                width="100%",
            ),
            rx.scroll_area(
                rx.hstack(
                    rx.foreach(JobDetailState.selected_job_tasks, task_pill),
                    spacing="3",
                    padding_bottom="2",
                    justify="center",
                ),
                scrollbars="horizontal",
                width="100%",
            ),
            rx.cond(
                JobDetailState.selected_task_id,
                rx.box(
                    rzp.group(
                        rzp.panel(
                            rx.scroll_area(
                                rx.code_block(
                                    JobDetailState.selected_task_yaml,
                                    language="yaml",
                                    width="100%",
                                    size="1",
                                ),
                                width="100%",
                                height="100%",
                            ),
                            default_size=40,
                            min_size=20,
                        ),
                        pretty_resize_handle(),
                        rzp.panel(
                            rx.box(
                                rx.cond(
                                    JobDetailState.selected_task_executions,
                                    rx.accordion.root(
                                        rx.foreach(
                                            JobDetailState.selected_task_executions_most_recent_first,
                                            execution_accordion_item,
                                        ),
                                        type="single",
                                        value=JobDetailState.selected_execution_id,
                                        on_value_change=JobDetailState.set_selected_execution_id,
                                        collapsible=True,
                                        variant="outline",
                                        width="100%",
                                    ),
                                    rx.text("No executions yet.", size="1", color="gray", padding="15px"),
                                ),
                                width="100%",
                                padding_left="3",
                            ),
                            default_size=60,
                            min_size=20,
                        ),
                        direction="horizontal",
                        auto_save_id="task-detail-panels",
                        style={"height": "500px"},
                        width="100%",
                    ),
                    width="100%",
                    padding_top="3",
                ),
                rx.fragment(),
            ),
            width="100%",
            spacing="3",
        ),
        width="100%",
        padding="10px",
    )

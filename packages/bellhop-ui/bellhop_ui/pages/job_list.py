import reflex as rx
import yaml
from bellhop_models.database import Job, Task, TaskExecution

from bellhop_ui.pages.job_detail import job_detail_section
from bellhop_ui.pages.shared import (
    APP_TITLE_SIZE,
    CONTENT_HEADER_SIZE,
    SECTION_TITLE_SIZE,
    small_task_success_diagram,
    state_badge,
)
from bellhop_ui.state import State


class JobTableState(rx.State):
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
    async def get_job(self, job_id: str):
        api_state = await self.get_state(State)
        job = await api_state.get_job(job_id)
        async with self:
            self.selected_job = job
            self.selected_task_id = ""
            self.selected_execution_id = ""


def job_row(job: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(job["name"]),
        rx.table.cell(job["description"]),
        rx.table.cell(state_badge(job["state"])),
        rx.table.cell(small_task_success_diagram(job)),
        rx.table.cell(job["next_execution_time"]),
        on_click=State.get_job(
            job["id"]
        ),  # TODO: rather than get job, just load the job from the jobs list into the detail view, no api call
        cursor="pointer",
        transition="background-color 0.15s ease",
        _hover={"background_color": rx.color("gray", 3)},
    )


def jobs_table() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading("Jobs", size=SECTION_TITLE_SIZE),
            width="100%",
            align="center",
        ),
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Description"),
                        rx.table.column_header_cell("State"),
                        rx.table.column_header_cell("Tasks"),
                        rx.table.column_header_cell("Next Execution"),
                    )
                ),
                rx.table.body(rx.foreach(State.jobs, job_row)),
                width="100%",
            ),
            width="100%",
        ),
        width="100%",
        padding="10px",
    )


def settings_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Change connection settings"),
            rx.form(
                rx.vstack(
                    rx.input(default_value=State.api_base_url, name="api_base_url"),
                    rx.input(
                        default_value=f"{State.api_jobs_poll_interval_seconds}",
                        name="api_jobs_poll_interval_seconds",
                        type="number",
                    ),
                    rx.flex(rx.dialog.close(rx.button("Submit", type="submit"))),
                ),
                on_submit=State.change_settings,
            ),
        ),
        open=State.settings_dialog_open,
        on_open_change=State.set_settings_dialog_open,
    )


def title_section() -> rx.Component:
    return rx.hstack(
        rx.heading("Bellhop", size=APP_TITLE_SIZE, align_self="center"),
        rx.spacer(),
        rx.cond(
            State.connected,
            rx.vstack(rx.foreach(State.api_environment_info, lambda item: rx.text(item[1], size=CONTENT_HEADER_SIZE))),
            rx.text("Disconnected", size=CONTENT_HEADER_SIZE, align_self="center"),
        ),
        rx.menu.root(
            rx.menu.trigger(rx.button(rx.icon("menu"))),
            rx.menu.content(rx.menu.item("Change connection settings", on_click=State.set_settings_dialog_open(True))),
        ),
        background_color=rx.color("gray", 3),
        padding="10px",
        width="100%",
    )


@rx.page(route="/", on_load=[State.get_environment, State.fetch_jobs, State.auto_refresh_jobs])
def job_list() -> rx.Component:
    return rx.vstack(
        title_section(),
        settings_dialog(),
        rx.box(
            rx.cond(
                State.selected_job,
                job_detail_section(),
                rx.fragment(),
            ),
            rx.separator(),
            jobs_table(),
            align="center",
            spacing="6",
            width="100%",
            min_height="100vh",
            style={"padding": "24px"},
        ),
    )

import reflex as rx
from bellhop_models.database import Task, TaskExecution
from reflex_resizable_panels import resizable_panels as rzp

from bellhop_ui.state import State

APP_TITLE_SIZE = "8"
SECTION_TITLE_SIZE = "5"
CONTENT_HEADER_SIZE = "2"
CONTENT_SIZE = "1"
ICON_SIZE = 18
CODE_FONT_SIZE = "var(--font-size-1)"

RESIZE_HANDLE_INNER: dict = {
    "height": "100%",
    "width": "100%",
    "display": "flex",
    "align_items": "center",
    "justify_content": "center",
    "background": rx.color("gray", 2),
    "border_left": f"1px solid {rx.color('gray', 5)}",
    "border_right": f"1px solid {rx.color('gray', 5)}",
    "cursor": "col-resize",
    "_hover": {"background": rx.color("accent", 3)},
}


def pretty_resize_handle() -> rx.Component:
    return (
        rzp.handle(
            rx.box(
                rx.icon("grip_vertical", size=16, color=rx.color("gray", 8)),
                **RESIZE_HANDLE_INNER,
            ),
            style={"width": "8px"},
        ),
    )


def state_badge_small(task: rx.Var) -> rx.Component:
    return rx.match(
        task["state"],
        (
            "Not Started",
            rx.tooltip(rx.badge(rx.icon("clock_10", size=ICON_SIZE), color_scheme="amber"), content=task["name"]),
        ),
        (
            "In Progress",
            rx.tooltip(
                rx.badge(rx.icon("loader", class_name="animate-spin", size=ICON_SIZE), color_scheme="blue"),
                content=task["name"],
            ),
        ),
        (
            "Completed",
            rx.tooltip(rx.badge(rx.icon("check", size=ICON_SIZE), color_scheme="green"), content=task["name"]),
        ),
        ("Errored", rx.tooltip(rx.badge(rx.icon("x", size=ICON_SIZE), color_scheme="red"), content=task["name"])),
        rx.badge("❔", color_scheme="gray"),
    )


def state_badge(state: rx.Var) -> rx.Component:
    return rx.match(
        state,
        ("Not Started", rx.badge("Not Started", color_scheme="amber")),
        ("In Progress", rx.badge("In Progress", color_scheme="blue")),
        ("Completed", rx.badge("Completed", color_scheme="green")),
        ("Errored", rx.badge("Errored", color_scheme="red")),
        rx.badge(state, color_scheme="gray"),
    )


def small_task_success_diagram(job: dict) -> rx.Component:
    return rx.hstack(
        rx.foreach(job["tasks"], lambda task: state_badge_small(task)),
    )


def job_row(job: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(job["name"]),
        rx.table.cell(job["description"]),
        rx.table.cell(state_badge(job["state"])),
        rx.table.cell(small_task_success_diagram(job)),
        rx.table.cell(job["next_execution_time"]),
        on_click=State.get_job(
            job["id"]
        ),  # rather than get job, just load the job from the jobs list into the detail view, no api call
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
        # border_left="2px solid var(--gray-5)",
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
    is_selected = task.id == State.selected_task_id
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
        on_click=State.set_selected_task_id(task.id),
        cursor="pointer",
        outline=rx.cond(is_selected, "2px solid var(--accent-9)", "none"),
        min_width="160px",
    )


def job_detail_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.grid(
                # rx.box(),
                rx.hstack(
                    rx.heading(State.selected_job.name, size="4"),
                    state_badge(State.selected_job.state),
                    align="center",
                ),
                rx.vstack(
                    rx.text(State.selected_job.description, size="2"),
                    rx.hstack(
                        rx.text("Submitted: ", State.selected_job.time_submitted, size="1", color="gray"),
                        rx.text("Originally scheduled: ", State.selected_job.time_scheduled, size="1", color="gray"),
                        rx.text("Next execution: ", State.selected_job.next_execution_time, size="1", color="gray"),
                        spacing="3",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.hstack(
                    rx.cond(
                        State.selected_job.state == "Not Started",
                        rx.button(
                            "Execute Now",
                            on_click=State.execute_now(State.selected_job.id),
                            size="1",
                        ),
                        rx.fragment(),
                    ),
                    rx.button(
                        "Retry",
                        on_click=State.retry_job(State.selected_job.id),
                        size="1",
                        variant="soft",
                    ),
                    rx.button(
                        "Abort",
                        on_click=State.abort_job(State.selected_job.id),
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
                    rx.foreach(State.selected_job_tasks, task_pill),
                    spacing="3",
                    padding_bottom="2",
                    justify="center",
                ),
                scrollbars="horizontal",
                width="100%",
            ),
            rx.cond(
                State.selected_task_id,
                rx.box(
                    rzp.group(
                        rzp.panel(
                            rx.scroll_area(
                                rx.code_block(
                                    State.selected_task_yaml,
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
                                    State.selected_task_executions,
                                    rx.accordion.root(
                                        rx.foreach(
                                            State.selected_task_executions_most_recent_first,
                                            execution_accordion_item,
                                        ),
                                        type="single",
                                        value=State.selected_execution_id,
                                        on_value_change=State.set_selected_execution_id,
                                        collapsible=True,
                                        variant="outline",
                                        width="100%",
                                    ),
                                    rx.text("No executions yet.", size="1", color="gray"),
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


def title_section() -> rx.Component:
    return rx.hstack(
        rx.heading("Bellhop", size=APP_TITLE_SIZE, align_self="center"),
        rx.spacer(),
        rx.vstack(rx.foreach(State.api_environment_info, lambda item: rx.text(item[1], size=CONTENT_HEADER_SIZE))),
        background_color=rx.color("gray", 3),
        padding="10px",
        width="100%",
    )


@rx.page(route="/", on_load=[State.get_environment, State.fetch_jobs, State.auto_refresh_jobs])
def job_list() -> rx.Component:
    return rx.vstack(
        title_section(),
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

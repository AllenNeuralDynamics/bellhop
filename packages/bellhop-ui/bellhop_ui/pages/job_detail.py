import reflex as rx
from bellhop_models.database import Task, TaskExecution
from reflex_resizable_panels import resizable_panels as rzp

from bellhop_ui.pages.shared import pretty_resize_handle, state_badge
from bellhop_ui.state import State


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

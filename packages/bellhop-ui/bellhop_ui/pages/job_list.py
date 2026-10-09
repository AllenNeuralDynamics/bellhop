import reflex as rx

from bellhop_ui.pages.job_detail import job_detail_section
from bellhop_ui.pages.job_list_state import JobTableState
from bellhop_ui.pages.shared import (
    SECTION_TITLE_SIZE,
    page_template,
    small_task_success_diagram,
    state_badge,
)


def job_row(job: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(job["name"]),
        rx.table.cell(job["description"]),
        rx.table.cell(state_badge(job["state"])),
        rx.table.cell(small_task_success_diagram(job)),
        rx.table.cell(job["next_execution_time"]),
        on_click=JobTableState.get_job(
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
                rx.table.body(rx.foreach(JobTableState.jobs, job_row)),
                width="100%",
            ),
            width="100%",
        ),
        width="100%",
        padding="10px",
    )


@rx.page(
    route="/",
    on_load=[
        JobTableState.init_page,
        JobTableState.auto_refresh_jobs,
        JobTableState.watch_tab_visibility,
    ],
)
@page_template
def job_list() -> rx.Component:
    return rx.box(
        rx.cond(
            JobTableState.selected_job,
            job_detail_section(),
            rx.fragment(),
        ),
        rx.separator(),
        jobs_table(),
    )

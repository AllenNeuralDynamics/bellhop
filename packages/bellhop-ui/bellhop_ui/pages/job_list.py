import asyncio
import logging

import reflex as rx
from bellhop_models import JobSummary

from bellhop_ui.bellhop_ui import app
from bellhop_ui.pages.job_detail import JobDetailState, job_detail_section
from bellhop_ui.pages.shared import (
    SECTION_TITLE_SIZE,
    page_template,
    small_task_success_diagram,
    state_badge,
)
from bellhop_ui.state import State, TabVisibilityMixin


class JobTableState(TabVisibilityMixin, State):
    """Job-list page state: the jobs table, polling and tab visibility.

    Inherits the shared base ``State`` so connection/settings vars are shared with
    the rest of the app; polls the jobs list independently from the job detail.
    """

    jobs: list[JobSummary] = []

    @rx.event
    def on_visible(self):
        # Tab came back; catch up immediately instead of waiting for the next poll tick.
        yield JobTableState.fetch_jobs

    async def _refresh_jobs(self) -> None:
        async with self:
            if not self.connected:
                return
            client = self.api_client

        # Let failures propagate so the calling background task can yield check_connection.
        jobs = await client.list_jobs()

        async with self:
            self.jobs = jobs

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


def job_row(job: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(job["name"]),
        rx.table.cell(job["description"]),
        rx.table.cell(state_badge(job["state"])),
        rx.table.cell(small_task_success_diagram(job)),
        rx.table.cell(job["next_execution_time"]),
        on_click=JobDetailState.get_job(
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
        JobDetailState.auto_refresh_job,
        JobDetailState.watch_tab_visibility,
        JobDetailState.parse_query_params,
    ],
)
@page_template
def job_list() -> rx.Component:
    return rx.box(
        rx.cond(
            JobDetailState.selected_job,
            job_detail_section(),
            rx.fragment(),
        ),
        rx.separator(),
        jobs_table(),
    )

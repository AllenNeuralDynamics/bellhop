from typing import Any

import reflex as rx
import yaml
from bellhop_models import JobSpecification
from pydantic import ValidationError
from reflex_resizable_panels import resizable_panels as rzp

from bellhop_ui.pages.shared import page_template, pretty_resize_handle
from bellhop_ui.state import State, api_call


def merge_variable_values(defaults: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    # Blank inputs submit empty strings; fall back to the template default for those.
    return {**defaults, **{key: value for key, value in raw.items() if value != ""}}


def validate_job_spec(job_yaml: str) -> str:
    """Validate job_yaml YAML against JobSpecification; empty string means valid."""
    if not job_yaml:
        return ""
    try:
        data = yaml.safe_load(job_yaml)
    except yaml.YAMLError as exc:
        return f"Invalid YAML: {exc}"
    try:
        JobSpecification.model_validate(data)
    except ValidationError as exc:
        errors = exc.errors()
        summary = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors)
        return f"{len(errors)} validation error(s): {summary}"
    return ""


class JobTemplatesState(State):
    """Templates page state. Inherits shared connection/settings; no job polling."""

    # Stage of the page state machine: "select" (pick a template) or "configure" (edit vars).
    stage: str = "select"

    all_template_names: list[str] = []
    selected_template_name: str = ""
    selected_template_content: str = ""
    selected_template_variables: list[str] = []
    selected_template_defaults: dict[str, str] = {}

    current_variable_values: dict[str, Any] = {}

    rendered_job: str = ""
    rendered_variable_values: dict[str, Any] = {}

    # Jobs submitted during this browser session, newest first.
    session_submitted_jobs: list[dict[str, str]] = []

    @rx.var
    def rendered_up_to_date(self) -> bool:
        effective = merge_variable_values(self.selected_template_defaults, self.current_variable_values)
        return bool(self.rendered_job) and effective == self.rendered_variable_values

    @rx.var
    def rendered_validation_error(self) -> str:
        """Validate the rendered YAML against JobSpecification; empty string means valid."""
        return validate_job_spec(self.rendered_job)

    @rx.var
    def rendered_is_valid(self) -> bool:
        return bool(self.rendered_job) and self.rendered_validation_error == ""

    def preview_template(self, template_name: str):
        self.selected_template_name = template_name
        self.current_variable_values = {}
        self.rendered_variable_values = {}
        self.rendered_job = ""
        yield JobTemplatesState.get_template_detail()

    def confirm_template_selection(self):
        if self.selected_template_name:
            self.stage = "configure"

    def discard_job(self):
        # Abandon the in-progress job and return to template selection.
        self.stage = "select"
        self.current_variable_values = {}
        self.rendered_job = ""
        self.rendered_variable_values = {}

    def set_variable_value(self, variable: str, value: str):
        self.current_variable_values[variable] = value

    def reset_state(self):
        self.stage = "select"
        self.selected_template_name = ""
        self.selected_template_content = ""
        self.selected_template_variables = []
        self.selected_template_defaults = {}
        self.current_variable_values = {}
        self.rendered_job = ""
        self.rendered_variable_values = {}

    ## API Calls

    @rx.event(background=True)
    @api_call
    async def get_template_list(self):
        async with self:
            client = self.api_client
        template_names = await client.list_templates()
        async with self:
            self.all_template_names = template_names

    @rx.event(background=True)
    @api_call
    async def get_template_detail(self):
        async with self:
            client = self.api_client
            template_name = self.selected_template_name
        template_content = await client.get_template(template_name)
        template_variables = await client.get_template_variables(template_name)
        template_defaults = await client.get_template_defaults(template_name)
        async with self:
            self.selected_template_content = template_content
            self.selected_template_variables = template_variables
            self.selected_template_defaults = template_defaults

    @rx.event(background=True)
    @api_call
    async def get_rendered_template(self, form_data: dict[str, Any]):
        async with self:
            client = self.api_client
            template_name = self.selected_template_name
            values = merge_variable_values(self.selected_template_defaults, form_data)
        rendered_template = await client.render_template_raw(template_name, values)
        async with self:
            self.rendered_job = rendered_template
            self.rendered_variable_values = values

    @rx.event(background=True)
    @api_call
    async def submit_job(self):
        async with self:
            client = self.api_client
            template_name = self.selected_template_name
            variables = self.rendered_variable_values
        try:
            submitted_job_uuid = await client.submit_template_job(template_name, variables)
        except Exception as e:
            yield rx.toast.error(f"Error submitting job: {e!r}")
            return
        async with self:
            self.session_submitted_jobs = [
                {"template": template_name, "job_id": str(submitted_job_uuid)},
                *self.session_submitted_jobs,
            ]
        yield rx.toast.success("Job submitted")
        yield JobTemplatesState.reset_state


def template_list_card() -> rx.Component:
    """Persistent, compact template list. Disabled while configuring a job."""
    disabled = JobTemplatesState.stage == "configure"
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("Job Templates", size="3"),
                rx.spacer(),
                rx.button(
                    rx.icon("refresh_ccw", size=14),
                    on_click=JobTemplatesState.get_template_list,
                    size="1",
                    disabled=disabled,
                ),
                width="100%",
                align="center",
            ),
            rx.scroll_area(
                rx.table.root(
                    rx.table.body(
                        rx.foreach(
                            JobTemplatesState.all_template_names,
                            lambda template_name: rx.table.row(
                                rx.table.cell(template_name),
                                on_click=lambda: JobTemplatesState.preview_template(template_name),
                                cursor="pointer",
                                transition="background-color 0.05s ease",
                                background_color=rx.cond(
                                    JobTemplatesState.selected_template_name == template_name,
                                    rx.color("accent", 4),
                                    "transparent",
                                ),
                                _hover={
                                    "background_color": rx.cond(
                                        JobTemplatesState.selected_template_name == template_name,
                                        rx.color("accent", 5),
                                        rx.color("gray", 3),
                                    )
                                },
                            ),
                        )
                    ),
                    width="100%",
                ),
                flex="1",
                min_height="0",
                width="100%",
                opacity=rx.cond(disabled, 0.5, 1),
                pointer_events=rx.cond(disabled, "none", "auto"),
            ),
            height="100%",
            width="100%",
            spacing="2",
        ),
        width="100%",
        height="100%",
    )


def submit_history_card() -> rx.Component:
    """Jobs submitted during this session."""
    return rx.card(
        rx.vstack(
            rx.heading("Submitted Jobs", size="3"),
            rx.cond(
                JobTemplatesState.session_submitted_jobs.length() == 0,
                rx.text("No jobs submitted yet this session.", color_scheme="gray", size="2"),
                rx.scroll_area(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Template"),
                                rx.table.column_header_cell("Job ID"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                JobTemplatesState.session_submitted_jobs,
                                lambda job: rx.table.row(
                                    rx.table.cell(job["template"]),
                                    rx.table.cell(rx.code(job["job_id"])),
                                ),
                            )
                        ),
                        width="100%",
                    ),
                    flex="1",
                    min_height="0",
                    width="100%",
                ),
            ),
            height="100%",
            width="100%",
            spacing="2",
        ),
        width="100%",
        height="100%",
    )


def template_preview_card() -> rx.Component:
    """Stage 1 right: read-only preview of the highlighted template."""
    return rx.card(
        rx.vstack(
            rx.heading("Template Preview", size="4"),
            rx.scroll_area(
                rx.cond(
                    JobTemplatesState.selected_template_content == "",
                    rx.text("Select a template to preview it here.", color_scheme="gray"),
                    rx.code_block(JobTemplatesState.selected_template_content, language="yaml"),
                ),
                flex="1",
                min_height="0",
                width="100%",
            ),
            height="100%",
            width="100%",
            spacing="3",
        ),
        width="100%",
        height="100%",
    )


def render_status_row() -> rx.Component:
    return rx.hstack(
        rx.cond(
            JobTemplatesState.rendered_up_to_date,
            rx.badge("Up to date", color_scheme="green", variant="soft"),
            rx.badge("Out of date", color_scheme="amber", variant="soft"),
        ),
        rx.cond(
            JobTemplatesState.rendered_job == "",
            rx.fragment(),
            rx.cond(
                JobTemplatesState.rendered_is_valid,
                rx.badge("Valid", color_scheme="green", variant="soft"),
                rx.tooltip(
                    rx.badge("Invalid", color_scheme="red", variant="soft"),
                    content=JobTemplatesState.rendered_validation_error,
                ),
            ),
        ),
        rx.spacer(),
        rx.button(
            "Submit Job",
            on_click=JobTemplatesState.submit_job,
            disabled=~(JobTemplatesState.rendered_up_to_date & JobTemplatesState.rendered_is_valid),
        ),
        width="100%",
        align="center",
    )


def configure_variables_card() -> rx.Component:
    """Stage 2 left: variable form and render controls."""
    return rx.card(
        rx.vstack(
            rx.heading("Variables", size="4"),
            rx.form(
                rx.scroll_area(
                    rx.table.root(
                        rx.table.body(
                            rx.foreach(
                                JobTemplatesState.selected_template_variables,
                                lambda variable: rx.table.row(
                                    rx.table.cell(variable),
                                    rx.table.cell(
                                        rx.input(
                                            placeholder=JobTemplatesState.selected_template_defaults.get(variable, ""),
                                            name=variable,
                                            on_change=lambda value, variable=variable: (
                                                JobTemplatesState.set_variable_value(variable, value)
                                            ),
                                        )
                                    ),
                                ),
                            )
                        ),
                        width="100%",
                    ),
                    flex="1",
                    min_height="0",
                    width="100%",
                ),
                rx.button("Render", type="submit", width="100%"),
                on_submit=JobTemplatesState.get_rendered_template,
                display="flex",
                flex_direction="column",
                gap="0.75rem",
                flex="1",
                min_height="0",
                width="100%",
            ),
            render_status_row(),
            height="100%",
            width="100%",
            spacing="3",
        ),
        width="100%",
        height="100%",
    )


def rendered_job_card() -> rx.Component:
    """Stage 2 right: rendered job preview."""
    return rx.card(
        rx.vstack(
            rx.heading("Rendered Job", size="4"),
            rx.scroll_area(
                rx.cond(
                    JobTemplatesState.rendered_job == "",
                    rx.text("Render the template to preview the job here.", color_scheme="gray"),
                    rx.code_block(JobTemplatesState.rendered_job, language="yaml"),
                ),
                flex="1",
                min_height="0",
                width="100%",
            ),
            height="100%",
            width="100%",
            spacing="3",
        ),
        width="100%",
        height="100%",
    )


def select_template_content() -> rx.Component:
    """Stage 1 right: template preview with the create-job call to action beside it."""
    return rx.hstack(
        rx.box(template_preview_card(), flex="1", min_width="0", height="100%"),
        rx.button(
            rx.icon("plus", size=30),
            "Create a new Job based on this template",
            rx.icon("arrow-right", size=16),
            on_click=JobTemplatesState.confirm_template_selection,
            disabled=JobTemplatesState.selected_template_name == "",
        ),
        height="100%",
        width="100%",
        spacing="3",
        align="start",
    )


def configure_new_job_content() -> rx.Component:
    """Stage 2: both panels under one in-progress job card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.badge("In progress", color_scheme="blue", variant="soft"),
                        rx.heading("New Job", size="4"),
                        spacing="2",
                        align="center",
                    ),
                    rx.text(
                        f"From template: {JobTemplatesState.selected_template_name}", size="1", color_scheme="gray"
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("trash-2", size=16),
                    "Discard",
                    on_click=JobTemplatesState.discard_job,
                    variant="soft",
                    color_scheme="red",
                ),
                width="100%",
                align="center",
            ),
            rx.divider(),
            rx.box(
                rzp.group(
                    rzp.panel(configure_variables_card(), default_size=50, min_size=20),
                    pretty_resize_handle(),
                    rzp.panel(rendered_job_card(), default_size=50, min_size=20),
                    direction="horizontal",
                    width="100%",
                    height="100%",
                ),
                flex="1",
                min_height="0",
                width="100%",
            ),
            height="100%",
            width="100%",
            spacing="3",
        ),
        width="100%",
        height="100%",
    )


@rx.page(route="/templates", on_load=[State.check_connection, JobTemplatesState.get_template_list])
@page_template
def job_templates() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.box(template_list_card(), flex="4", min_height="0", width="100%"),
            rx.box(submit_history_card(), flex="6", min_height="0", width="100%"),
            width="340px",
            height="100%",
            spacing="3",
        ),
        rx.box(
            rx.cond(
                JobTemplatesState.stage == "select",
                select_template_content(),
                configure_new_job_content(),
            ),
            flex="1",
            min_width="0",
            height="100%",
        ),
        width="100%",
        height="100%",
        spacing="3",
        align="stretch",
    )

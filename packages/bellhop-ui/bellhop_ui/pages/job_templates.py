import reflex as rx

from bellhop_ui.pages.shared import page_template
from bellhop_ui.state import State


class JobTemplatesState(State):
    """Templates page state. Inherits shared connection/settings; no job polling."""

def job_templates_table() -> rx.Component:
    return rx.box(
        
    )

@rx.page(route="/templates", on_load=[State.check_connection])
@page_template
def job_templates() -> rx.Component:
    return rx.text("Job Templates Page")

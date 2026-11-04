from collections.abc import Callable

import reflex as rx
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
        rx.heading("Bellhop", size=APP_TITLE_SIZE, align_self="center", padding_left="15px"),
        rx.spacer(),
        rx.cond(
            State.connected,
            rx.vstack(rx.foreach(State.api_environment_info, lambda item: rx.text(item[1], size=CONTENT_HEADER_SIZE))),
            rx.vstack(
                rx.text("Disconnected", size=CONTENT_HEADER_SIZE, align_self="center"),
                rx.button(rx.icon("refresh_ccw"), on_click=State.check_connection, size="1", align_self="center"),
            ),
        ),
        rx.menu.root(
            rx.menu.trigger(rx.button(rx.icon("menu"))),
            rx.menu.content(rx.menu.item("Change connection settings", on_click=State.set_settings_dialog_open(True))),
        ),
        background_color=rx.color("gray", 3),
        padding="10px",
        width="100%",
    )


def side_bar_button(icon: str, label: str, route: str) -> rx.Component:
    return rx.tooltip(
        rx.link(
            rx.button(
                rx.icon(icon, size=ICON_SIZE),
                variant="ghost",
                color_scheme="gray",
                size="3",
                width="40px",
                height="40px",
            ),
            href=route,
        ),
        content=label,
        side="right",
    )


def side_bar() -> rx.Component:
    return rx.vstack(
        side_bar_button("table", "Jobs", "/"),
        side_bar_button("Plus", "Templates", "/templates"),
        spacing="3",
        align="center",
        padding="10px",
        background_color=rx.color("gray", 2),
        height="100%",
    )


def page_template(page: Callable[[], rx.Component]) -> rx.Component:
    return rx.vstack(
        title_section(),
        settings_dialog(),
        rx.hstack(
            side_bar(),
            rx.box(
                page(),
                align="center",
                spacing="6",
                width="100%",
                height="100%",
                overflow_y="auto",
                style={"padding": "24px"},
            ),
            spacing="0",
            width="100%",
            align="start",
            flex="1",
            min_height="0",
        ),
        spacing="0",
        width="100%",
        height="100vh",
        overflow="hidden",
    )

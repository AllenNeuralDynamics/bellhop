import reflex as rx
from reflex_resizable_panels import resizable_panels as rzp

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

from bellhop_models.database import Job
import reflex as rx

from bellhop.api import app as fastapi_app


class State(rx.State):
    jobs: list[Job] = []


def index() -> rx.Component:
    return rx.text("Hello, World!")


app = rx.App(api_transformer=fastapi_app)
app.page(index)

import functools
import inspect
import logging

import reflex as rx
from bellhop_client import AsyncBellhopClient

from bellhop_ui.services.api_client import ClientRegistry


def api_call(fn):
    """Run a background job action only when connected, reconnecting on failure.

    The wrapped handler runs only if ``self.connected``; any exception is turned
    into a ``check_connection`` event instead of bubbling out of the task.
    """
    is_async_gen = inspect.isasyncgenfunction(fn)

    @functools.wraps(fn)
    async def wrapper(self, *args, **kwargs):
        async with self:
            if not self.connected:
                return
        try:
            if is_async_gen:
                async for event in fn(self, *args, **kwargs):
                    yield event
            else:
                await fn(self, *args, **kwargs)
        except Exception:
            logging.exception("job action failed")
            yield State.check_connection

    return wrapper


class TabVisibilityMixin(rx.State, mixin=True):
    """Tracks browser tab visibility and calls ``on_visible`` when the tab returns.

    Page states mix this in and override ``on_visible`` to react (e.g. refresh data).
    Arm it from a page's ``on_load`` via ``watch_tab_visibility``.
    """

    tab_visible: bool = True

    @rx.event
    def watch_tab_visibility(self):
        # Resolve once the tab's visibility changes, then re-arm in set_tab_visible.
        return rx.call_script(
            "new Promise((resolve) => document.addEventListener("
            "'visibilitychange', () => resolve(document.visibilityState), {once: true}))",
            callback=type(self).set_tab_visible,
        )

    @rx.event
    def set_tab_visible(self, visibility: str):
        self.tab_visible = visibility == "visible"
        if self.tab_visible:
            yield type(self).on_visible
        yield type(self).watch_tab_visibility

    @rx.event
    def on_visible(self):
        """Hook called when the tab becomes visible; override in page states."""


class State(rx.State):
    """Shared base state: connection status, settings and environment info.

    Page-specific states (e.g. ``JobTableState``) inherit from this, so these
    vars are shared across the app while each page keeps its own data/behavior.
    """

    api_jobs_poll_interval_seconds: int = 5
    api_base_url: str = "http://localhost:8312"
    connected: bool = False
    api_environment_info: dict[str, str] = {}
    settings_dialog_open: bool = False

    @property
    def client_id(self) -> str:
        """Returns unique token for this browser session."""
        return self.router.session.client_token or "default_session"

    @property
    def api_client(self) -> AsyncBellhopClient:
        """Helper to safely access the per-session client in any event or background task."""
        return ClientRegistry.get_client(self.client_id, self.api_base_url)

    @rx.event
    def set_settings_dialog_open(self, open: bool) -> None:
        self.settings_dialog_open = open

    @rx.event
    async def change_settings(self, new_values: dict):
        if (new_url := new_values.get("api_base_url")) and new_url != self.api_base_url:
            self.api_base_url = new_url
            await ClientRegistry.update_client(self.client_id, self.api_base_url)
            self.api_environment_info = {}

        if new_interval := new_values.get("api_jobs_poll_interval_seconds"):
            self.api_jobs_poll_interval_seconds = int(new_interval)

        # Reconnect; page states fetch their own data once connected.
        yield State.check_connection

    @rx.event  # TODO: Call this from on_disconnect from a page
    async def on_disconnect(self):
        """Called automatically when a browser tab closes / disconnects."""
        client_token = self.router.session.client_token
        if client_token:
            await ClientRegistry.remove_client(client_token)

    ## API calls

    @rx.event(background=True)
    async def check_connection(self):
        async with self:
            client = self.api_client

        # Network I/O must happen OUTSIDE the state lock, otherwise this session's
        # events (renders, clicks, page loads) are blocked for the whole request.
        try:
            await client.health_check()
        except Exception:
            logging.exception("failed to connect")
            async with self:
                self.connected = False
            return

        async with self:
            self.connected = True

        # Page states drive their own data loads; here we just refresh shared info.
        yield State.get_environment

    @rx.event(background=True)
    @api_call
    async def get_environment(self):
        async with self:
            client = self.api_client
        environment = await client.get_environment()
        async with self:
            self.api_environment_info = environment

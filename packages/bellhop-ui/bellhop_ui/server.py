"""Run the Reflex UI (backend + pre-compiled frontend) in-process.

Reflex's own ``run_backend_prod`` spawns ``python -m uvicorn`` as a subprocess,
which is impossible inside a frozen PyInstaller exe. Instead we point Reflex at a
pre-exported frontend (``reflex export``), mount it on the backend, and run
uvicorn in-process against the app factory.

This module must NOT import the app module (``bellhop_ui.bellhop_ui``) at module
load time, and the package ``__init__`` must stay empty: the app's event handlers
register into whichever RegistrationContext (a contextvar) is active when the app
module is first imported. The UI runs in a daemon thread, so the first import
must happen inside that thread after the context is set up, or the serving
thread ends up with an empty handler registry.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path


def _base_dir() -> Path:
    """Directory containing ``rxconfig.py`` and the exported ``.web`` build."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # dev: the bellhop-ui project dir is the parent of this package.
    return Path(__file__).resolve().parent.parent


def _configure_reflex(base_dir: Path) -> None:
    # Reflex loads rxconfig.py from the current working directory, so run from
    # the project root. bellhop's own paths are absolute, so this is safe.
    os.chdir(base_dir)
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

    os.environ["REFLEX_WEB_WORKDIR"] = str(base_dir / ".web")

    from reflex.config import reload_config
    from reflex.environment import environment
    from reflex.utils import prerequisites

    # These internal env vars are only honored via the typed API, not os.environ.
    environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP.set(True)
    environment.REFLEX_SKIP_COMPILE.set(True)

    # In a frozen app there is no reflex project tree; bypass the checks that
    # assume one and the app-name/folder validation.
    prerequisites.assert_in_reflex_dir = lambda: None
    prerequisites._check_app_name = lambda config: setattr(config, "_app_name_is_valid", True)

    # get_config() may already have cached an empty config from the old cwd;
    # reload it now that we're in the project root.
    reload_config()


def _build_asgi_app():
    from reflex.utils import prerequisites

    # First import of the app module happens here, in the serving thread, so its
    # event handlers register into the context this thread serves with.
    app_module = prerequisites.get_app()
    return app_module.app()  # rx.App.__call__ -> ASGI app with frontend mounted


def run_ui(host: str = "0.0.0.0", port: int = 8311) -> None:
    """Serve the Reflex UI (blocking)."""
    import uvicorn

    _configure_reflex(_base_dir())
    uvicorn.run(_build_asgi_app(), host=host, port=port, log_level="info")


def start_ui_thread(host: str = "0.0.0.0", port: int = 8311) -> threading.Thread:
    """Serve the Reflex UI in a daemon thread and return it."""
    thread = threading.Thread(target=run_ui, args=(host, port), daemon=True, name="reflex-ui")
    thread.start()
    return thread


if __name__ == "__main__":
    run_ui()

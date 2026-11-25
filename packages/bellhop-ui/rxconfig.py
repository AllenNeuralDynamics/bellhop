import os

import reflex as rx

config = rx.Config(
    app_name="bellhop_ui",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ],
    frontend_port=8311,
    # Production bundles frontend+backend on one port; export sets this so the
    # compiled frontend talks to the right backend. Dev (`reflex run`) keeps :8000.
    api_url=os.environ.get("BELLHOP_UI_API_URL", "http://localhost:8000"),
    show_built_with_reflex=False,
)

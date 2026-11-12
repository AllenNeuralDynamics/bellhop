import reflex as rx

app = rx.App()

# Pages import `app` from this module, so they must be imported after it is
# defined. Importing them here (rather than in the package __init__) keeps
# `import bellhop_ui` side-effect free; see bellhop_ui/server.py.
from bellhop_ui.pages import job_list, job_templates  # noqa: E402, F401

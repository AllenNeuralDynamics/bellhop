import json
import multiprocessing
from pathlib import Path
from typing import Literal

import yaml
from cyclopts import App

from bellhop import __version__
from bellhop.api import app as fastapi_app, main
from bellhop.config import Config
from bellhop.self_test import run_self_test
from bellhop.servy import setup_service

cli_app = App(version=__version__)


@cli_app.command
def config_schema(file: Path | None = None) -> dict:
    """Return the jsonschema for the Config class.

    Args:
        file: Optional Path to write the schema to as a JSON file.
    """
    schema = Config.model_json_schema()
    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("w") as f:
            json.dump(schema, f, indent=2)
    return json.dumps(schema)


@cli_app.command
def openapi_spec(
    file: Path | None = None,
    format: Literal["yaml", "json"] = "yaml",
) -> dict:
    spec = fastapi_app.openapi()
    format = file.suffix.lstrip(".") if file is not None else format
    if format == "json":
        spec_serialized = json.dumps(spec, indent=2)
    elif format == "yaml":
        spec_serialized = yaml.dump(spec, sort_keys=False)
    else:
        raise ValueError(f"Unsupported format: {format}")

    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("w") as f:
            f.write(spec_serialized)
    return spec_serialized


cli_app.command(run_self_test)
cli_app.command(setup_service)

cli_app.default(main)

if __name__ == "__main__":
    multiprocessing.freeze_support()  # intercept spawned workers before CLI parsing (frozen exe)
    cli_app()

"""Commands for managing the Bellhop service with servy.

Usage: main service COMMAND

╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ export-servy-config  Export Bellhop's current service configuration to a file or just to console.                                                                                                                                                                                                                       │
│ install              Write a Servy JSON service configuration and use it to install Bellhop as a service.                                                                                                                                                                                                               │
│ make-servy-config    Write a Servy JSON service configuration based on current bellhop settings                                                                                                                                                                                                                         │
│ restart              Restart the Bellhop service.                                                                                                                                                                                                                                                                       │
│ servy-version        Display the Servy version information.                                                                                                                                                                                                                                                             │
│ show                 Show the Bellhop service details.                                                                                                                                                                                                                                                                  │
│ start                Start the Bellhop service.                                                                                                                                                                                                                                                                         │
│ status               Check the status of the Bellhop service.                                                                                                                                                                                                                                                           │
│ stop                 Stop the Bellhop service.                                                                                                                                                                                                                                                                          │
│ ui                   Open the Servy Manager UI.                                                                                                                                                                                                                                                                         │
│ uninstall            Uninstall the Bellhop service.                                                                                                                                                                                                                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Any, Literal

from cyclopts import App, Parameter
from pydantic import BaseModel, ConfigDict, Field

from bellhop.config import Config

DEFAULT_SERVICE_NAME = "Bellhop"
DEFAULT_DISPLAY_NAME = "Bellhop Service"
DEFAULT_DESCRIPTION = "Bellhop job orchestration API and web UI"
DEFAULT_CONFIG_FILENAME = "bellhop_servy.json"

StartupType = Literal["Automatic", "AutomaticDelayedStart", "Manual", "Disabled"]
ProcessPriority = Literal["Idle", "BelowNormal", "Normal", "AboveNormal", "High", "RealTime"]
RecoveryAction = Literal["None", "RestartService", "RestartProcess", "RestartComputer"]

STARTUP_TYPE_CODES: dict[StartupType, int] = {
    "Automatic": 2,
    "Manual": 3,
    "Disabled": 4,
    "AutomaticDelayedStart": 5,
}

PRIORITY_CODES: dict[ProcessPriority, int] = {
    "Idle": 0,
    "BelowNormal": 1,
    "Normal": 2,
    "AboveNormal": 3,
    "High": 4,
    "RealTime": 5,
}

RECOVERY_ACTION_CODES: dict[RecoveryAction, int] = {
    "None": 0,
    "RestartService": 1,
    "RestartProcess": 2,
    "RestartComputer": 3,
}


class ServyOptions(BaseModel):
    """Servy Windows service configuration options."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = DEFAULT_SERVICE_NAME
    display_name: str = DEFAULT_DISPLAY_NAME
    description: str = DEFAULT_DESCRIPTION
    executable_path: Path | None = None
    startup_dir: Path | None = None
    params: str | None = None
    startup_type: StartupType = "Automatic"
    priority: ProcessPriority = "Normal"
    start_timeout: int = Field(default=30, ge=1, le=86400)
    stop_timeout: int = Field(default=15, ge=1, le=86400)
    log_dir: Path | None = None
    rotation_size_mb: int = Field(default=10, ge=1, le=10240)
    max_rotations: int = Field(default=5, ge=0, le=10000)
    enable_health: bool = True
    heartbeat_interval: int = Field(default=30, ge=5, le=86400)
    max_failed_checks: int = Field(default=3, ge=1, le=100000)
    recovery_action: RecoveryAction = "RestartService"
    max_restart_attempts: int = Field(default=3, ge=0, le=100000)
    heartbeat_url: str | None = None
    heartbeat_url_timeout: int = Field(default=5, ge=2, le=30)
    enable_heartbeat_url_flags: bool = False
    env_vars: str | None = None


DEFAULT_SERVY_OPTIONS = ServyOptions()


def _is_administrator() -> bool:
    """Return True if the current process is running with Administrator (or root) privileges."""
    if os.name == "nt":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _resolve_servy_cli(servy_cli: Path | None = None) -> Path:
    """Locate `servy-cli` from an explicit path, `PATH`, or the default Windows install directory."""
    if servy_cli is not None:
        cli_path = Path(servy_cli)
        if not cli_path.is_file():
            raise FileNotFoundError(
                f"servy-cli executable not found at '{cli_path}'. "
                "Verify the path passed to --servy-cli or install Servy (https://github.com/aelassas/servy)."
            )
        return cli_path

    for exe_name in ("servy-cli", "servy-cli.exe"):
        found = shutil.which(exe_name)
        if found:
            return Path(found)

    if os.name == "nt":
        for env_var in ("ProgramW6432", "ProgramFiles"):
            program_files = os.environ.get(env_var)
            if program_files:
                candidate = Path(program_files) / "Servy" / "servy-cli.exe"
                if candidate.is_file():
                    return candidate

    raise FileNotFoundError(
        "Could not find 'servy-cli' on PATH or in 'C:\\Program Files\\Servy\\servy-cli.exe'. "
        "Install Servy (e.g. 'choco install servy' or https://github.com/aelassas/servy/releases), "
        "add it to your PATH, or pass --servy-cli <path>."
    )


def _resolve_bellhop_executable(
    executable_path: Path | None = None,
    startup_dir: Path | None = None,
) -> tuple[Path, Path, list[str]]:
    """Resolve `(executable_path, startup_dir, base_args)` for the current Bellhop runtime.
    Bellhop can run from a pyinstaller executable or within a python environment."""

    if executable_path is not None:
        exe = Path(executable_path).resolve()
        resolved_dir = Path(startup_dir).resolve() if startup_dir is not None else exe.parent
        return exe, resolved_dir, []

    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        resolved_dir = Path(startup_dir).resolve() if startup_dir is not None else exe.parent
        return exe, resolved_dir, []

    script_name = "bellhop.exe" if os.name == "nt" else "bellhop"
    venv_script = Path(sys.executable).with_name(script_name)
    if venv_script.is_file():
        exe = venv_script.resolve()
        resolved_dir = Path(startup_dir).resolve() if startup_dir is not None else exe.parent
        return exe, resolved_dir, []

    which_bellhop = shutil.which("bellhop")
    if which_bellhop:
        exe = Path(which_bellhop).resolve()
        resolved_dir = Path(startup_dir).resolve() if startup_dir is not None else exe.parent
        return exe, resolved_dir, []

    py_exe = Path(sys.executable).resolve()
    resolved_dir = Path(startup_dir).resolve() if startup_dir is not None else Path.cwd().resolve()
    return py_exe, resolved_dir, ["-m", "bellhop.cli"]


def _run_servy_command(
    command: str,
    *,
    name: str = DEFAULT_SERVICE_NAME,
    servy_cli: Path | None = None,
    extra_args: list[str] | None = None,
    require_administrator: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run one Servy CLI command and report its error consistently."""
    if require_administrator and not _is_administrator():
        print(f"Permission denied: Administrator privileges are required to {command} the service.", file=sys.stderr)
        sys.exit(1)  # Exit with a non-zero status code if administrator privileges are required

    cli_path = _resolve_servy_cli(servy_cli)
    args = [str(cli_path), command]
    if name is not None:
        args.extend(["--name", name])
    if extra_args:
        args.extend(extra_args)

    try:
        output = subprocess.run(args, check=True, capture_output=True, text=True)
        if output.stdout:
            print(output.stdout, end="" if output.stdout.endswith("\n") else "\n")
        return output
    except subprocess.CalledProcessError as e:
        details = (e.stderr or e.stdout or "").strip()
        print(f"Error running Servy {command}: {details}", file=sys.stderr)
        raise


def build_servy_config(
    config: Config | None = None,
    options: ServyOptions = DEFAULT_SERVY_OPTIONS,
    *,
    forwarded_config_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Servy `ServiceDto` dictionary dynamically from Bellhop's `Config`, `ServyOptions`, and runtime."""
    cfg = config if config is not None else Config()
    exe_path, resolved_startup_dir, base_args = _resolve_bellhop_executable(
        options.executable_path,
        options.startup_dir,
    )

    resolved_log_dir = options.log_dir if options.log_dir is not None else cfg.data_dir / "logs"
    stdout_path = resolved_log_dir / f"{options.name.lower()}-stdout.log"
    stderr_path = resolved_log_dir / f"{options.name.lower()}-stderr.log"

    cli_tokens = list(base_args)
    if forwarded_config_args:
        for key, value in forwarded_config_args.items():
            cli_tokens.extend([f"--{key}", str(value)])

    param_parts: list[str] = []
    if cli_tokens:
        param_parts.append(subprocess.list2cmdline(cli_tokens))
    if options.params:
        param_parts.append(options.params)
    combined_params = " ".join(param_parts)

    resolved_heartbeat_url = (
        f"http://127.0.0.1:{cfg.api_port}/" if options.heartbeat_url is None else options.heartbeat_url
    )

    dto: dict[str, Any] = {
        "Name": options.name,
        "DisplayName": options.display_name,
        "Description": options.description,
        "ExecutablePath": str(exe_path),
        "StartupDirectory": str(resolved_startup_dir),
        "StartupType": STARTUP_TYPE_CODES[options.startup_type],
        "Priority": PRIORITY_CODES[options.priority],
        "StdoutPath": str(stdout_path),
        "StderrPath": str(stderr_path),
        "StartTimeout": options.start_timeout,
        "StopTimeout": options.stop_timeout,
        "EnableConsoleUI": False,
        "EnableSizeRotation": True,
        "RotationSize": options.rotation_size_mb,
        "EnableDateRotation": False,
        "DateRotationType": 3,
        "MaxRotations": options.max_rotations,
        "UseLocalTimeForRotation": True,
        "EnableDebugLogs": False,
        "EnableHealthMonitoring": options.enable_health,
        "HeartbeatInterval": options.heartbeat_interval,
        "MaxFailedChecks": options.max_failed_checks,
        "RecoveryAction": RECOVERY_ACTION_CODES[options.recovery_action],
        "MaxRestartAttempts": options.max_restart_attempts,
        "RecoveryOnCleanExit": False,
    }

    if combined_params:
        dto["Parameters"] = combined_params

    if options.enable_health and resolved_heartbeat_url:
        dto["HeartbeatUrl"] = resolved_heartbeat_url
        dto["HeartbeatUrlTimeoutSeconds"] = options.heartbeat_url_timeout
        dto["EnableHeartbeatUrlFlags"] = options.enable_heartbeat_url_flags

    if options.env_vars:
        dto["EnvironmentVariables"] = options.env_vars

    return dto


def make_servy_config(
    file: Path | None = None,
    *,
    options: ServyOptions = DEFAULT_SERVY_OPTIONS,
    **config_kwargs: Any,
) -> Path:
    """Write a Servy JSON service configuration based on current bellhop settings"""
    normalized_kwargs = {k.replace("-", "_"): v for k, v in config_kwargs.items()}
    cfg = Config(**normalized_kwargs)
    dto = build_servy_config(cfg, options, forwarded_config_args=normalized_kwargs)

    output_path = Path(file) if file is not None else cfg.data_dir / DEFAULT_CONFIG_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Path(dto["StdoutPath"]).parent.mkdir(parents=True, exist_ok=True)
    Path(dto["StderrPath"]).parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(json.dumps(dto, indent=2) + "\n", encoding="utf-8")

    return output_path


def setup_servy_from_config(
    config_path: Path,
    install: bool = True,
    servy_cli: Path | None = None,
) -> None:
    """Run `servy-cli import` to set up a service from a config file."""
    args = ["-c", "json", "-p", str(config_path), "--quiet"]
    if install:
        args.append("--install")

    _run_servy_command(
        "import",
        name=None,
        servy_cli=servy_cli,
        extra_args=args,
    )


def install(
    file: Path | None = None,
    *,
    install: bool = True,
    servy_cli: Path | None = None,
    options: Annotated[ServyOptions, Parameter(name="*")] = DEFAULT_SERVY_OPTIONS,
    start_after_install: Annotated[bool, Parameter(name="--start")] = True,
    **config_kwargs: Any,
) -> None:
    """Write a Servy JSON service configuration and use it to install Bellhop as a service.

    Extra keyword options matching `Config` fields (for example `--api-port 9000` or `--data-dir ...`)
    are applied to both the generated Servy settings (log paths, `HeartbeatUrl`) and forwarded into
    the service `Parameters` so Bellhop launches with the same configuration.
    """
    if install and not _is_administrator():
        raise PermissionError("Administrator privileges are required to install the service.")
    output_path = make_servy_config(file, options=options, **config_kwargs)
    setup_servy_from_config(output_path, install=install, servy_cli=servy_cli)
    if start_after_install:
        start(name=options.name, servy_cli=servy_cli)


def uninstall(
    name: str = DEFAULT_SERVICE_NAME,
    servy_cli: Path | None = None,
) -> None:
    """Uninstall the Bellhop service."""
    _run_servy_command("uninstall", name=name, servy_cli=servy_cli, require_administrator=True)


def start(
    name: str = DEFAULT_SERVICE_NAME,
    servy_cli: Path | None = None,
) -> None:
    """Start the Bellhop service."""
    _run_servy_command("start", name=name, servy_cli=servy_cli, require_administrator=True)


def stop(
    name: str = DEFAULT_SERVICE_NAME,
    servy_cli: Path | None = None,
) -> None:
    """Stop the Bellhop service."""
    _run_servy_command("stop", name=name, servy_cli=servy_cli, require_administrator=True)


def restart(
    name: str = DEFAULT_SERVICE_NAME,
    servy_cli: Path | None = None,
) -> None:
    """Restart the Bellhop service."""
    _run_servy_command("restart", name=name, servy_cli=servy_cli, require_administrator=True)


def status(
    name: str = DEFAULT_SERVICE_NAME,
    servy_cli: Path | None = None,
) -> None:
    """Check the status of the Bellhop service."""
    _run_servy_command("status", name=name, servy_cli=servy_cli)


def export_servy_config(
    path: Path | None = None,
    *,
    name: str = DEFAULT_SERVICE_NAME,
    config: Literal["json", "yaml"] = "json",
    servy_cli: Path | None = None,
    file: Path | None = None,
) -> Path | str:
    """Export Bellhop's current service configuration to a file or just to console."""
    destination = path if path is not None else file
    if destination is None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temporary_path = Path(temp_dir) / f"servy-export.{config}"
            export_servy_config(temporary_path, name=name, config=config, servy_cli=servy_cli)
            return temporary_path.read_text(encoding="utf-8")

    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    _run_servy_command(
        "export",
        name=name,
        servy_cli=servy_cli,
        extra_args=["--config", config, "--path", str(destination)],
        require_administrator=True,
    )
    return destination


def show(
    name: str = DEFAULT_SERVICE_NAME,
    decrypt: bool = False,
    servy_cli: Path | None = None,
) -> None:
    """Show the Bellhop service details."""
    extra_args = ["--decrypt"] if decrypt else None
    _run_servy_command("show", name=name, servy_cli=servy_cli, extra_args=extra_args, require_administrator=True)


def servy_version() -> None:
    """Display the Servy version information."""
    _run_servy_command("version")


def ui() -> None:
    """Open the Servy Manager UI."""
    cli_path = _resolve_servy_cli().parent
    try:
        output = subprocess.run([cli_path / "Servy.Manager.exe"], check=True, capture_output=True, text=True)
        if output.stdout:
            print(output.stdout, end="" if output.stdout.endswith("\n") else "\n")
        return output
    except subprocess.CalledProcessError as e:
        details = (e.stderr or e.stdout or "").strip()
        print(f"Error running Servy ui: {details}", file=sys.stderr)
        raise


cli_app = App()
cli_app.command(install)
cli_app.command(make_servy_config)
cli_app.command(export_servy_config)
cli_app.command(uninstall)
cli_app.command(start)
cli_app.command(stop)
cli_app.command(restart)
cli_app.command(status)
cli_app.command(show)
cli_app.command(servy_version)
cli_app.command(ui)

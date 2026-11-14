import ctypes
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Literal

from cyclopts import App

from bellhop.config import Config

DEFAULT_SERVICE_NAME = "Bellhop"
DEFAULT_DISPLAY_NAME = "Bellhop Service"
DEFAULT_DESCRIPTION = "Bellhop job orchestration API and web UI"
DEFAULT_HEARTBEAT_URL = "http://localhost:8312"

StartupType = Literal["Automatic", "AutomaticDelayedStart", "Manual", "Disabled"]
ProcessPriority = Literal["Idle", "BelowNormal", "Normal", "AboveNormal", "High", "RealTime"]
RecoveryAction = Literal["None", "RestartService", "RestartProcess", "RestartComputer"]
DateRotationType = Literal["Daily", "Weekly", "Monthly", "None"]
ConfigFormat = Literal["json", "xml"]


class ServiceStatus(StrEnum):
    NOT_INSTALLED = "NotInstalled"
    STOPPED = "Stopped"
    START_PENDING = "StartPending"
    STOP_PENDING = "StopPending"
    RUNNING = "Running"
    CONTINUE_PENDING = "ContinuePending"
    PAUSE_PENDING = "PausePending"
    PAUSED = "Paused"
    UNKNOWN = "Unknown"


class ServyError(RuntimeError):
    """Raised when a Servy CLI invocation fails."""

    def __init__(
        self,
        message: str,
        *,
        command: list[str] | None = None,
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ServyNotFoundError(ServyError, FileNotFoundError):
    """Raised when servy-cli.exe cannot be located."""


class ServyPermissionError(ServyError, PermissionError):
    """Raised when an operation requires Administrator privileges."""


def default_bellhop_executable() -> Path:
    """Return the default Bellhop executable path.

    When running from a frozen PyInstaller bundle, returns ``Path(sys.executable)``.
    Otherwise checks ``C:\\Program Files\\AllenInstitute\\bellhop\\bellhop.exe`` and the
    Chocolatey ``tools`` directory, falling back to the Program Files path.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()

    # Prefer ProgramW6432 so 32-bit Python on 64-bit Windows still resolves 64-bit Program Files.
    program_files = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles") or r"C:\Program Files"
    program_files_exe = Path(program_files) / "AllenInstitute" / "bellhop" / "bellhop.exe"
    if program_files_exe.is_file():
        return program_files_exe

    choco_root = os.environ.get("ChocolateyInstall") or r"C:\ProgramData\chocolatey"
    choco_exe = Path(choco_root) / "lib" / "bellhop" / "tools" / "bellhop.exe"
    if choco_exe.is_file():
        return choco_exe

    return program_files_exe


def find_servy_cli(servy_cli: Path | str | None = None) -> Path:
    """Locate `servy-cli.exe` from an explicit path, `SERVY_CLI_PATH`, Program Files, or `PATH`."""
    if servy_cli is not None:
        explicit = Path(servy_cli)
        if explicit.is_file():
            return explicit
        raise ServyNotFoundError(f"Servy CLI executable not found at '{explicit}'.")

    env_override = os.environ.get("SERVY_CLI_PATH")
    if env_override:
        env_path = Path(env_override)
        if env_path.is_file():
            return env_path
        raise ServyNotFoundError(f"SERVY_CLI_PATH points to a non-existent file: '{env_path}'.")

    candidates: list[Path] = []
    for var in ("ProgramW6432", "ProgramFiles"):
        pf = os.environ.get(var)
        if pf:
            candidates.append(Path(pf) / "Servy" / "servy-cli.exe")
    candidates.append(Path(r"C:\Program Files\Servy\servy-cli.exe"))

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    for exe_name in ("servy-cli.exe", "servy-cli"):
        found = shutil.which(exe_name)
        if found:
            return Path(found)

    raise ServyNotFoundError(
        "Could not find 'servy-cli.exe'. Install Servy (https://github.com/aelassas/servy) "
        "or set SERVY_CLI_PATH / pass servy_cli explicitly."
    )


def is_admin() -> bool:
    """Return True if the current process has elevated Administrator privileges."""
    if os.name == "nt":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def format_servy_env_vars(env_vars: Mapping[str, str] | str) -> str:
    """Format environment variables for Servy (`KEY=VALUE;KEY2=VALUE2`).

    When given a mapping, escapes literal `\\`, `=`, `"`, `;`, and `%` characters per Servy's
    escaping rules. Pass a pre-formatted `str` directly if you want Servy `%VAR%` expansion.
    """
    if isinstance(env_vars, str):
        return env_vars

    parts: list[str] = []
    for key, value in env_vars.items():
        clean_key = key.strip()
        if not clean_key or any(ch in clean_key for ch in ("=", ";", "\r", "\n")):
            raise ValueError(f"Invalid environment variable name: {key!r}")
        escaped_val = (
            str(value)
            .replace("\\", "\\\\")
            .replace("=", "\\=")
            .replace('"', '\\"')
            .replace(";", "\\;")
            .replace("%", "%%")
        )
        parts.append(f"{clean_key}={escaped_val}")
    return ";".join(parts)


def _run_servy(
    subcommand: str,
    args: Sequence[str] = (),
    *,
    env_overrides: Mapping[str, str] | None = None,
    quiet: bool = True,
    require_admin: bool = True,
    servy_cli: Path | str | None = None,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    if require_admin and os.name == "nt" and not is_admin():
        raise ServyPermissionError(
            f"Servy '{subcommand}' requires Administrator privileges. Run from an elevated terminal."
        )

    cli_path = find_servy_cli(servy_cli)
    cmd = [str(cli_path), subcommand, *args]
    if quiet:
        cmd.append("--quiet")

    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise ServyError(
            f"servy-cli {subcommand} failed: {details}",
            command=cmd,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    return result


def servy_version(*, servy_cli: Path | None = None) -> str:
    """Return the installed Servy CLI version string."""
    result = _run_servy("version", quiet=True, require_admin=False, servy_cli=servy_cli)
    return result.stdout.strip()


def install_service(
    *,
    name: str = DEFAULT_SERVICE_NAME,
    executable_path: Path | None = None,
    startup_dir: Path | None = None,
    params: str | list[str] | None = None,
    display_name: str = DEFAULT_DISPLAY_NAME,
    description: str = DEFAULT_DESCRIPTION,
    startup_type: StartupType = "Automatic",
    priority: ProcessPriority = "Normal",
    start_timeout: int = 30,
    stop_timeout: int = 15,
    enable_log_rotation: bool = True,
    log_dir: Path | None = None,
    stdout_log: Path | None = None,
    stderr_log: Path | None = None,
    rotation_size_mb: int = 10,
    enable_date_rotation: bool = False,
    date_rotation_type: DateRotationType | None = None,
    max_rotations: int = 5,
    use_local_time_for_rotation: bool = True,
    enable_health: bool = True,
    heartbeat_interval: int = 30,
    max_failed_checks: int = 3,
    recovery_action: RecoveryAction = "RestartService",
    max_restart_attempts: int = 3,
    recovery_on_clean_exit: bool = False,
    heartbeat_url: str | None = DEFAULT_HEARTBEAT_URL,
    heartbeat_url_timeout: int | None = None,
    enable_heartbeat_url_flags: bool = False,
    env_vars: dict[str, str] | str | None = None,
    deps: list[str] | str | None = None,
    user: str | None = None,
    password: str | None = None,
    start: bool = False,
    check_executable: bool = True,
    servy_cli: Path | None = None,
    quiet: bool = True,
) -> str:
    """Install (or update) the Bellhop Windows service via Servy.

    Note: `RestartService` and `RestartComputer` recovery actions require LocalSystem or an
    account with service control privileges; use `recovery_action="RestartProcess"` for
    restricted service accounts such as `NT AUTHORITY\\LocalService`.
    """
    exe_path = Path(executable_path) if executable_path is not None else default_bellhop_executable()
    if check_executable and not exe_path.is_file():
        raise FileNotFoundError(
            f"Bellhop executable not found at '{exe_path}'. Install Bellhop first or pass executable_path explicitly."
        )

    resolved_startup_dir = Path(startup_dir) if startup_dir is not None else exe_path.parent

    args: list[str] = [
        f"--name={name}",
        f"--path={exe_path}",
        f"--startupDir={resolved_startup_dir}",
        f"--displayName={display_name}",
        f"--description={description}",
        f"--startupType={startup_type}",
        f"--priority={priority}",
        f"--startTimeout={start_timeout}",
        f"--stopTimeout={stop_timeout}",
    ]

    if enable_log_rotation or log_dir is not None or stdout_log is not None or stderr_log is not None:
        stdout_opt = Path(stdout_log) if stdout_log is not None else None
        stderr_opt = Path(stderr_log) if stderr_log is not None else None
        if stdout_opt is None or stderr_opt is None:
            resolved_log_dir = Path(log_dir) if log_dir is not None else Config().data_dir / "logs"
            resolved_log_dir.mkdir(parents=True, exist_ok=True)
            stdout_path = stdout_opt if stdout_opt is not None else resolved_log_dir / f"{name.lower()}-stdout.log"
            stderr_path = stderr_opt if stderr_opt is not None else resolved_log_dir / f"{name.lower()}-stderr.log"
        else:
            stdout_path = stdout_opt
            stderr_path = stderr_opt

        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        args.append(f"--stdout={stdout_path}")
        args.append(f"--stderr={stderr_path}")

        if enable_log_rotation:
            args.append("--enableSizeRotation")
            args.append(f"--rotationSize={rotation_size_mb}")
            args.append(f"--maxRotations={max_rotations}")
            if use_local_time_for_rotation:
                args.append("--useLocalTimeForRotation")

        if enable_date_rotation:
            args.append("--enableDateRotation")
            args.append(f"--dateRotationType={date_rotation_type or 'Daily'}")

    if enable_health:
        args.append("--enableHealth")
        args.append(f"--heartbeatInterval={heartbeat_interval}")
        args.append(f"--maxFailedChecks={max_failed_checks}")
        args.append(f"--recoveryAction={recovery_action}")
        args.append(f"--maxRestartAttempts={max_restart_attempts}")
        if recovery_on_clean_exit:
            args.append("--recoveryOnCleanExit")
        if heartbeat_url_timeout is not None:
            args.append(f"--heartbeatUrlTimeoutSeconds={heartbeat_url_timeout}")
        if enable_heartbeat_url_flags:
            args.append("--enableHeartbeatUrlFlags")

    if deps is not None:
        deps_str = deps if isinstance(deps, str) else ";".join(deps)
        if deps_str:
            args.append(f"--deps={deps_str}")

    if user is not None:
        args.append(f"--user={user}")

    # Pass sensitive/complex options through Servy's environment variables rather than CLI argv
    # so they are never exposed in OS process listings.
    env_overrides: dict[str, str] = {}
    if params is not None:
        env_overrides["SERVY_PROCESS_PARAMETERS"] = (
            params if isinstance(params, str) else subprocess.list2cmdline(params)
        )
    if env_vars is not None:
        env_overrides["SERVY_ENVIRONMENT_VARIABLES"] = format_servy_env_vars(env_vars)
    if password is not None:
        env_overrides["SERVY_PASSWORD"] = password
    if enable_health and heartbeat_url is not None:
        env_overrides["SERVY_HEARTBEAT_URL"] = heartbeat_url

    install_res = _run_servy(
        "install",
        args,
        env_overrides=env_overrides,
        quiet=quiet,
        require_admin=True,
        servy_cli=servy_cli,
    )
    output = install_res.stdout.strip()

    if start:
        start_out = start_service(name=name, servy_cli=servy_cli, quiet=quiet)
        return "\n".join(part for part in (output, start_out) if part)
    return output


def uninstall_service(
    name: str = DEFAULT_SERVICE_NAME,
    *,
    servy_cli: Path | None = None,
    quiet: bool = True,
) -> str:
    """Uninstall the Windows service via Servy."""
    result = _run_servy("uninstall", [f"--name={name}"], quiet=quiet, require_admin=True, servy_cli=servy_cli)
    return result.stdout.strip()


def start_service(
    name: str = DEFAULT_SERVICE_NAME,
    *,
    servy_cli: Path | None = None,
    quiet: bool = True,
) -> str:
    """Start the Windows service via Servy."""
    result = _run_servy("start", [f"--name={name}"], quiet=quiet, require_admin=True, servy_cli=servy_cli)
    return result.stdout.strip()


def stop_service(
    name: str = DEFAULT_SERVICE_NAME,
    *,
    servy_cli: Path | None = None,
    quiet: bool = True,
) -> str:
    """Stop the Windows service via Servy."""
    result = _run_servy("stop", [f"--name={name}"], quiet=quiet, require_admin=True, servy_cli=servy_cli)
    return result.stdout.strip()


def restart_service(
    name: str = DEFAULT_SERVICE_NAME,
    *,
    servy_cli: Path | None = None,
    quiet: bool = True,
) -> str:
    """Restart the Windows service via Servy."""
    result = _run_servy("restart", [f"--name={name}"], quiet=quiet, require_admin=True, servy_cli=servy_cli)
    return result.stdout.strip()


def service_status(
    name: str = DEFAULT_SERVICE_NAME,
    *,
    servy_cli: Path | None = None,
    quiet: bool = True,
) -> ServiceStatus:
    """Query the current status of the Windows service via Servy (does not require elevation)."""
    result = _run_servy("status", [f"--name={name}"], quiet=quiet, require_admin=False, servy_cli=servy_cli)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return ServiceStatus.UNKNOWN

    # servy-cli outputs e.g. "Service status for 'Bellhop': Running"
    last_line = lines[-1]
    token = last_line.rsplit(":", 1)[-1].strip()
    try:
        return ServiceStatus(token)
    except ValueError:
        return ServiceStatus.UNKNOWN


def is_service_installed(name: str = DEFAULT_SERVICE_NAME, *, servy_cli: Path | None = None) -> bool:
    """Return True if the service is currently installed."""
    return service_status(name=name, servy_cli=servy_cli) != ServiceStatus.NOT_INSTALLED


def is_service_running(name: str = DEFAULT_SERVICE_NAME, *, servy_cli: Path | None = None) -> bool:
    """Return True if the service is currently in the `Running` state."""
    return service_status(name=name, servy_cli=servy_cli) == ServiceStatus.RUNNING


def show_service(
    name: str | None = DEFAULT_SERVICE_NAME,
    *,
    all_services: bool = False,
    search: str | None = None,
    decrypt: bool = False,
    servy_cli: Path | None = None,
    quiet: bool = True,
) -> str:
    """Show a stored Servy service configuration (or list services with `all_services=True` / `search`)."""
    args: list[str] = []
    if all_services:
        if search is not None:
            raise ValueError("Cannot specify both 'all_services=True' and 'search'.")
        if decrypt:
            raise ValueError(
                "'decrypt=True' requires a specific service 'name' and cannot be used with 'all_services'."
            )
    elif search is not None:
        if name is not None and name != DEFAULT_SERVICE_NAME:
            raise ValueError("Cannot specify both 'name' and 'search' when calling show_service.")
        if decrypt:
            raise ValueError("'decrypt=True' requires a specific service 'name' and cannot be used with 'search'.")
        args.append(f"--search={search}")
    elif name is not None:
        args.append(f"--name={name}")
        if decrypt:
            args.append("--decrypt")
    elif decrypt:
        raise ValueError("'decrypt=True' requires a specific service 'name'.")

    result = _run_servy("show", args, quiet=quiet, require_admin=True, servy_cli=servy_cli)
    return result.stdout.strip()


def _resolve_config_format(path: Path, config_format: ConfigFormat | None) -> ConfigFormat:
    if config_format is not None:
        return config_format
    ext = path.suffix.lower().lstrip(".")
    if ext in ("json", "xml"):
        return ext  # type: ignore[return-value]
    if not ext:
        return "json"
    raise ValueError(f"Unsupported config file extension '.{ext}'; expected '.json' or '.xml'.")


def export_service_config(
    path: Path,
    *,
    name: str = DEFAULT_SERVICE_NAME,
    config_format: ConfigFormat | None = None,
    servy_cli: Path | None = None,
    quiet: bool = True,
) -> Path:
    """Export a Servy service configuration to a JSON or XML file."""
    out_path = Path(path)
    fmt = _resolve_config_format(out_path, config_format)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run_servy(
        "export",
        [f"--name={name}", f"--config={fmt}", f"--path={out_path}"],
        quiet=quiet,
        require_admin=True,
        servy_cli=servy_cli,
    )
    return out_path


def import_service_config(
    path: Path,
    *,
    install: bool = True,
    config_format: ConfigFormat | None = None,
    servy_cli: Path | None = None,
    quiet: bool = True,
) -> str:
    """Import a Servy JSON or XML service configuration and optionally install the service."""
    in_path = Path(path)
    if not in_path.is_file():
        raise FileNotFoundError(f"Service configuration file not found: '{in_path}'.")
    fmt = _resolve_config_format(in_path, config_format)
    args = [f"--config={fmt}", f"--path={in_path}"]
    if install:
        args.append("--install")
    result = _run_servy("import", args, quiet=quiet, require_admin=True, servy_cli=servy_cli)
    return result.stdout.strip()


service_app = App(name="service", help="Manage the Bellhop Windows service via Servy.")
service_app.command(install_service, name="install")
service_app.command(uninstall_service, name="uninstall")
service_app.command(start_service, name="start")
service_app.command(stop_service, name="stop")
service_app.command(restart_service, name="restart")
service_app.command(service_status, name="status")
service_app.command(show_service, name="show")
service_app.command(export_service_config, name="export")
service_app.command(import_service_config, name="import")
service_app.command(servy_version, name="version")

import subprocess
from pathlib import Path

import pytest

from bellhop import service
from bellhop.config import Config
from bellhop.service import (
    DEFAULT_DESCRIPTION,
    DEFAULT_DISPLAY_NAME,
    DEFAULT_SERVICE_NAME,
    ServiceStatus,
    ServyError,
    ServyNotFoundError,
    ServyPermissionError,
    default_bellhop_executable,
    export_service_config,
    find_servy_cli,
    format_servy_env_vars,
    import_service_config,
    install_service,
    is_service_installed,
    is_service_running,
    restart_service,
    service_status,
    servy_version,
    show_service,
    start_service,
    stop_service,
    uninstall_service,
)


@pytest.fixture
def fake_servy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli_exe = tmp_path / "servy-cli.exe"
    cli_exe.write_text("stub")
    monkeypatch.setattr(service, "is_admin", lambda: True)

    calls: list[dict] = []
    responses: list[subprocess.CompletedProcess[str]] = []

    def fake_run(cmd, *, capture_output, text, env, timeout, check):
        calls.append({"cmd": cmd, "env": env, "timeout": timeout})
        if responses:
            return responses.pop(0)
        return subprocess.CompletedProcess(cmd, 0, stdout="OK\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return cli_exe, calls, responses


def test_default_bellhop_executable_prefers_programw6432(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delattr("sys.frozen", raising=False)
    monkeypatch.setenv("ProgramW6432", r"C:\Program Files")
    monkeypatch.setenv("ProgramFiles", r"C:\Program Files (x86)")
    monkeypatch.setenv("ChocolateyInstall", str(tmp_path / "empty_choco"))
    assert default_bellhop_executable() == Path(r"C:\Program Files\AllenInstitute\bellhop\bellhop.exe")


def test_default_bellhop_executable_frozen_and_chocolatey(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    choco_root = tmp_path / "choco"
    choco_exe = choco_root / "lib" / "bellhop" / "tools" / "bellhop.exe"
    choco_exe.parent.mkdir(parents=True)
    choco_exe.write_text("exe")

    monkeypatch.delattr("sys.frozen", raising=False)
    monkeypatch.setenv("ProgramW6432", str(tmp_path / "empty_pf"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "empty_pf"))
    monkeypatch.setenv("ChocolateyInstall", str(choco_root))
    assert default_bellhop_executable() == choco_exe

    frozen_exe = tmp_path / "frozen" / "bellhop.exe"
    frozen_exe.parent.mkdir(parents=True)
    frozen_exe.write_text("exe")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(frozen_exe))
    assert default_bellhop_executable() == frozen_exe.resolve()


def test_find_servy_cli_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli_file = tmp_path / "servy-cli.exe"
    cli_file.write_text("stub")

    assert find_servy_cli(cli_file) == cli_file

    with pytest.raises(ServyNotFoundError):
        find_servy_cli(tmp_path / "missing.exe")

    monkeypatch.setenv("SERVY_CLI_PATH", str(cli_file))
    assert find_servy_cli() == cli_file

    monkeypatch.setenv("SERVY_CLI_PATH", str(tmp_path / "nope.exe"))
    with pytest.raises(ServyNotFoundError):
        find_servy_cli()

    monkeypatch.delenv("SERVY_CLI_PATH")
    monkeypatch.setenv("ProgramW6432", str(tmp_path / "empty_pf"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "empty_pf"))
    monkeypatch.setattr("shutil.which", lambda _: None)
    # Also ensure fallback C:\Program Files\Servy\servy-cli.exe doesn't satisfy test when absent
    orig_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda self: False if "Servy" in str(self) else orig_is_file(self))
    with pytest.raises(ServyNotFoundError):
        find_servy_cli()


def test_format_servy_env_vars():
    formatted = format_servy_env_vars(
        {
            "BELLHOP_DATA_DIR": r"C:\ProgramData\Bellhop",
            "COMPLEX": 'a=b;c"d%e',
        }
    )
    assert formatted == r"BELLHOP_DATA_DIR=C:\\ProgramData\\Bellhop;COMPLEX=a\=b\;c\"d%%e"

    raw = r"DATA=%ProgramData%\Bellhop"
    assert format_servy_env_vars(raw) == raw

    with pytest.raises(ValueError):
        format_servy_env_vars({"BAD=KEY": "1"})


def test_install_service_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_servy):
    cli_exe, calls, _ = fake_servy
    bellhop_exe = tmp_path / "install" / "bellhop.exe"
    bellhop_exe.parent.mkdir(parents=True)
    bellhop_exe.write_text("exe")

    data_dir = tmp_path / "data"
    monkeypatch.setattr(service, "Config", lambda: Config(data_dir=data_dir))
    monkeypatch.setattr(service, "default_bellhop_executable", lambda: bellhop_exe)

    out = install_service(servy_cli=cli_exe)
    assert out == "OK"
    assert len(calls) == 1

    cmd = calls[0]["cmd"]
    assert cmd[0] == str(cli_exe)
    assert cmd[1] == "install"
    assert f"--name={DEFAULT_SERVICE_NAME}" in cmd
    assert f"--path={bellhop_exe}" in cmd
    assert f"--startupDir={bellhop_exe.parent}" in cmd
    assert f"--displayName={DEFAULT_DISPLAY_NAME}" in cmd
    assert f"--description={DEFAULT_DESCRIPTION}" in cmd
    assert "--startupType=Automatic" in cmd
    assert f"--stdout={data_dir / 'logs' / 'bellhop-stdout.log'}" in cmd
    assert f"--stderr={data_dir / 'logs' / 'bellhop-stderr.log'}" in cmd
    assert "--enableSizeRotation" in cmd
    assert "--rotationSize=10" in cmd
    assert "--maxRotations=5" in cmd
    assert "--useLocalTimeForRotation" in cmd
    assert "--enableHealth" in cmd
    assert "--heartbeatInterval=30" in cmd
    assert "--maxFailedChecks=3" in cmd
    assert "--recoveryAction=RestartService" in cmd
    assert "--maxRestartAttempts=3" in cmd
    assert "--quiet" in cmd


def test_install_service_secure_env_and_start(tmp_path: Path, fake_servy):
    cli_exe, calls, responses = fake_servy
    bellhop_exe = tmp_path / "bellhop.exe"
    bellhop_exe.write_text("exe")

    responses.append(subprocess.CompletedProcess([], 0, stdout="Installed\n", stderr=""))
    responses.append(subprocess.CompletedProcess([], 0, stdout="Started\n", stderr=""))

    out = install_service(
        name="BellhopRig1",
        executable_path=bellhop_exe,
        params=["--api-port", "9000"],
        env_vars={"AIBS_COMP_ID": "RIG-01"},
        user=r".\svc_bellhop",
        password="secret-password",
        heartbeat_url="https://hc-ping.com/uuid",
        deps=["Tcpip", "Dnscache"],
        enable_log_rotation=False,
        start=True,
        servy_cli=cli_exe,
    )

    assert out == "Installed\nStarted"
    assert len(calls) == 2

    install_cmd = calls[0]["cmd"]
    install_env = calls[0]["env"]
    # Secrets and env vars must be passed via Servy environment variables, never CLI flags.
    joined_cmd = " ".join(install_cmd)
    assert "secret-password" not in joined_cmd
    assert "RIG-01" not in joined_cmd
    assert "hc-ping.com" not in joined_cmd
    assert "--deps=Tcpip;Dnscache" in install_cmd
    assert r"--user=.\svc_bellhop" in install_cmd
    assert "--enableSizeRotation" not in install_cmd
    assert install_env["SERVY_PROCESS_PARAMETERS"] == "--api-port 9000"
    assert install_env["SERVY_ENVIRONMENT_VARIABLES"] == "AIBS_COMP_ID=RIG-01"
    assert install_env["SERVY_PASSWORD"] == "secret-password"
    assert install_env["SERVY_HEARTBEAT_URL"] == "https://hc-ping.com/uuid"

    start_cmd = calls[1]["cmd"]
    assert start_cmd == [str(cli_exe), "start", "--name=BellhopRig1", "--quiet"]


def test_install_service_missing_executable(tmp_path: Path, fake_servy):
    cli_exe, _, _ = fake_servy
    with pytest.raises(FileNotFoundError):
        install_service(executable_path=tmp_path / "missing.exe", servy_cli=cli_exe)


def test_lifecycle_and_status_commands(monkeypatch: pytest.MonkeyPatch, fake_servy):
    cli_exe, calls, responses = fake_servy

    start_service("Bellhop", servy_cli=cli_exe)
    stop_service("Bellhop", servy_cli=cli_exe)
    restart_service("Bellhop", servy_cli=cli_exe)
    uninstall_service("Bellhop", servy_cli=cli_exe)

    assert [c["cmd"][1] for c in calls] == ["start", "stop", "restart", "uninstall"]

    # status and version should NOT require Administrator privileges even on Windows
    monkeypatch.setattr(service, "is_admin", lambda: False)
    responses.append(subprocess.CompletedProcess([], 0, stdout="Service status for 'Bellhop': Running\n", stderr=""))
    status = service_status("Bellhop", servy_cli=cli_exe)
    assert status is ServiceStatus.RUNNING
    assert status == "Running"

    responses.append(subprocess.CompletedProcess([], 0, stdout="Service status for 'Bellhop': Running\n", stderr=""))
    assert is_service_running("Bellhop", servy_cli=cli_exe) is True

    responses.append(
        subprocess.CompletedProcess([], 0, stdout="Service status for 'Bellhop': NotInstalled\n", stderr="")
    )
    assert is_service_installed("Bellhop", servy_cli=cli_exe) is False

    responses.append(subprocess.CompletedProcess([], 0, stdout="Servy.CLI 10.7.0\n", stderr=""))
    assert servy_version(servy_cli=cli_exe) == "Servy.CLI 10.7.0"


def test_show_export_import(tmp_path: Path, fake_servy):
    cli_exe, calls, _ = fake_servy

    show_service(decrypt=True, servy_cli=cli_exe)
    assert calls[-1]["cmd"] == [str(cli_exe), "show", "--name=Bellhop", "--decrypt", "--quiet"]

    show_service(all_services=True, servy_cli=cli_exe)
    assert calls[-1]["cmd"] == [str(cli_exe), "show", "--quiet"]

    show_service(search="Bellhop", servy_cli=cli_exe)
    assert calls[-1]["cmd"] == [str(cli_exe), "show", "--search=Bellhop", "--quiet"]

    with pytest.raises(ValueError):
        show_service(all_services=True, decrypt=True, servy_cli=cli_exe)

    cfg_path = tmp_path / "configs" / "bellhop.json"
    exported = export_service_config(cfg_path, servy_cli=cli_exe)
    assert exported == cfg_path
    assert calls[-1]["cmd"] == [
        str(cli_exe),
        "export",
        "--name=Bellhop",
        "--config=json",
        f"--path={cfg_path}",
        "--quiet",
    ]

    cfg_path.write_text("{}")
    import_service_config(cfg_path, install=True, servy_cli=cli_exe)
    assert calls[-1]["cmd"] == [
        str(cli_exe),
        "import",
        "--config=json",
        f"--path={cfg_path}",
        "--install",
        "--quiet",
    ]


def test_permission_and_cli_errors(monkeypatch: pytest.MonkeyPatch, fake_servy):
    cli_exe, _, responses = fake_servy

    responses.append(subprocess.CompletedProcess([], 1, stdout="", stderr="Service not found"))
    with pytest.raises(ServyError) as exc_info:
        start_service("Bellhop", servy_cli=cli_exe)
    assert exc_info.value.returncode == 1
    assert "Service not found" in str(exc_info.value)

    if service.os.name == "nt":
        monkeypatch.setattr(service, "is_admin", lambda: False)
        with pytest.raises(ServyPermissionError):
            start_service("Bellhop", servy_cli=cli_exe)

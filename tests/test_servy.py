import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from bellhop import servy
from bellhop.cli import cli_app
from bellhop.config import Config
from bellhop.servy import (
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_DESCRIPTION,
    DEFAULT_DISPLAY_NAME,
    DEFAULT_SERVICE_NAME,
    ServyOptions,
    _is_administrator,
    _resolve_bellhop_executable,
    _resolve_servy_cli,
    build_servy_config,
    export_servy_config,
    install,
    make_servy_config,
    restart,
    show,
    start,
    status,
    stop,
    uninstall,
)


def test_resolve_bellhop_executable_frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_exe = tmp_path / "Program Files" / "bellhop" / "bellhop.exe"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.write_text("exe")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    exe, startup_dir, base_args = _resolve_bellhop_executable()
    assert exe == fake_exe.resolve()
    assert startup_dir == fake_exe.parent.resolve()
    assert base_args == []


def test_resolve_bellhop_executable_python_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_py = tmp_path / "venv" / "python.exe"
    fake_py.parent.mkdir(parents=True)
    fake_py.write_text("py")

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_py))
    monkeypatch.setattr(servy.shutil, "which", lambda _: None)

    exe, startup_dir, base_args = _resolve_bellhop_executable(startup_dir=tmp_path)
    assert exe == fake_py.resolve()
    assert startup_dir == tmp_path.resolve()
    assert base_args == ["-m", "bellhop.cli"]


def test_servy_options_validation():
    with pytest.raises(ValidationError):
        ServyOptions(heartbeat_interval=1)  # below Servy minimum of 5s
    with pytest.raises(ValidationError):
        ServyOptions(unknown_option="x")  # type: ignore[call-arg]


def test_build_servy_config_defaults(tmp_path: Path):
    fake_exe = tmp_path / "bin" / "bellhop.exe"
    cfg = Config(data_dir=tmp_path / "programdata", api_port=8312)

    dto = build_servy_config(cfg, ServyOptions(executable_path=fake_exe))

    assert dto["Name"] == DEFAULT_SERVICE_NAME
    assert dto["DisplayName"] == DEFAULT_DISPLAY_NAME
    assert dto["Description"] == DEFAULT_DESCRIPTION
    assert dto["ExecutablePath"] == str(fake_exe.resolve())
    assert dto["StartupDirectory"] == str(fake_exe.parent.resolve())
    assert dto["StartupType"] == 2
    assert dto["Priority"] == 2
    assert dto["StdoutPath"] == str(cfg.data_dir / "logs" / "bellhop-stdout.log")
    assert dto["StderrPath"] == str(cfg.data_dir / "logs" / "bellhop-stderr.log")
    assert dto["EnableSizeRotation"] is True
    assert dto["RotationSize"] == 10
    assert dto["DateRotationType"] == 3
    assert dto["MaxRotations"] == 5
    assert dto["UseLocalTimeForRotation"] is True
    assert dto["EnableHealthMonitoring"] is True
    assert dto["HeartbeatInterval"] == 30
    assert dto["MaxFailedChecks"] == 3
    assert dto["RecoveryAction"] == 1
    assert dto["MaxRestartAttempts"] == 3
    assert dto["HeartbeatUrl"] == "http://127.0.0.1:8312/"
    assert dto["HeartbeatUrlTimeoutSeconds"] == 5
    assert dto["EnableHeartbeatUrlFlags"] is False
    assert "Parameters" not in dto


def test_is_administrator_returns_bool():
    assert isinstance(_is_administrator(), bool)


def test_resolve_servy_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    custom_cli = tmp_path / "custom" / "servy-cli.exe"
    custom_cli.parent.mkdir(parents=True)
    custom_cli.write_text("stub")

    assert _resolve_servy_cli(custom_cli) == custom_cli

    with pytest.raises(FileNotFoundError, match="not found at"):
        _resolve_servy_cli(tmp_path / "missing-servy-cli.exe")

    monkeypatch.setattr(servy.shutil, "which", lambda name: str(custom_cli) if name == "servy-cli" else None)
    assert _resolve_servy_cli() == custom_cli

    monkeypatch.setattr(servy.shutil, "which", lambda _: None)
    monkeypatch.setenv("ProgramW6432", str(tmp_path / "no_servy"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "no_servy"))
    with pytest.raises(FileNotFoundError, match="--servy-cli"):
        _resolve_servy_cli()


def test_make_servy_config_and_cli_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_exe = tmp_path / "app" / "bellhop.exe"
    fake_servy_cli = tmp_path / "servy" / "servy-cli.exe"
    fake_servy_cli.parent.mkdir(parents=True)
    fake_servy_cli.write_text("stub")
    data_dir = tmp_path / ("programdata_" + "x" * 90)
    opts = ServyOptions(
        name="BellhopRig1",
        executable_path=fake_exe,
        startup_type="AutomaticDelayedStart",
        recovery_action="RestartProcess",
        env_vars="AIBS_COMP_ID=RIG-01",
    )

    written = make_servy_config(
        options=opts,
        **{"data-dir": str(data_dir), "api-port": "9005", "serve-ui": "false"},
    )

    assert written == data_dir / DEFAULT_CONFIG_FILENAME
    assert written.is_file()
    assert (data_dir / "logs").is_dir()

    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["Name"] == "BellhopRig1"
    assert payload["StartupType"] == 5
    assert payload["RecoveryAction"] == 2
    assert payload["HeartbeatUrl"] == "http://127.0.0.1:9005/"
    assert payload["StdoutPath"] == str(data_dir / "logs" / "bellhoprig1-stdout.log")
    assert payload["EnvironmentVariables"] == "AIBS_COMP_ID=RIG-01"
    assert "--data_dir" in payload["Parameters"]
    assert str(data_dir) in payload["Parameters"]
    assert "--api_port 9005" in payload["Parameters"]
    assert "--serve_ui false" in payload["Parameters"]

    monkeypatch.setattr(servy, "_is_administrator", lambda: False)
    with pytest.raises(PermissionError, match="Administrator privileges"):
        install(options=opts, install=True, servy_cli=fake_servy_cli, **{"data-dir": str(data_dir)})

    monkeypatch.setattr(servy, "_is_administrator", lambda: True)
    with pytest.raises(FileNotFoundError, match="not found at"):
        install(
            options=opts,
            install=True,
            servy_cli=tmp_path / "missing-cli.exe",
            **{"data-dir": str(data_dir)},
        )

    calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: calls.append(args) or subprocess.CompletedProcess(args, 0),
    )

    # Verify Cyclopts flattens ServyOptions and passes --servy-cli alongside Config kwargs
    cli_app(
        [
            "service",
            "install",
            "--servy-cli",
            str(fake_servy_cli),
            "--name",
            "BellhopFromCli",
            "--executable-path",
            str(fake_exe),
            "--data-dir",
            str(data_dir),
            "--api-port",
            "9010",
        ],
        result_action="return_value",
    )
    assert calls == [[str(fake_servy_cli), "import", "-c", "json", "-p", str(written), "--quiet", "--install"]]
    cli_payload = json.loads(written.read_text(encoding="utf-8"))
    assert cli_payload["Name"] == "BellhopFromCli"
    assert cli_payload["HeartbeatUrl"] == "http://127.0.0.1:9010/"


def test_servy_management_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_servy_cli = tmp_path / "servy" / "servy-cli.exe"
    fake_servy_cli.parent.mkdir(parents=True)
    fake_servy_cli.write_text("stub")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: calls.append(args) or subprocess.CompletedProcess(args, 0, stdout=""),
    )
    monkeypatch.setattr(servy, "_is_administrator", lambda: True)

    status(name="BellhopRig1", servy_cli=fake_servy_cli)
    start(name="BellhopRig1", servy_cli=fake_servy_cli)
    stop(name="BellhopRig1", servy_cli=fake_servy_cli)
    restart(name="BellhopRig1", servy_cli=fake_servy_cli)
    uninstall(name="BellhopRig1", servy_cli=fake_servy_cli)

    exported = tmp_path / "bellhop.json"
    assert export_servy_config(exported, name="BellhopRig1", servy_cli=fake_servy_cli) == exported
    show(name="BellhopRig1", decrypt=True, servy_cli=fake_servy_cli)

    assert calls == [
        [str(fake_servy_cli), "status", "--name", "BellhopRig1"],
        [str(fake_servy_cli), "start", "--name", "BellhopRig1"],
        [str(fake_servy_cli), "stop", "--name", "BellhopRig1"],
        [str(fake_servy_cli), "restart", "--name", "BellhopRig1"],
        [str(fake_servy_cli), "uninstall", "--name", "BellhopRig1"],
        [str(fake_servy_cli), "export", "--name", "BellhopRig1", "--config", "json", "--path", str(exported)],
        [str(fake_servy_cli), "show", "--name", "BellhopRig1", "--decrypt"],
    ]


def test_export_without_file_prints_contents_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    fake_servy_cli = tmp_path / "servy-cli.exe"
    fake_servy_cli.write_text("stub")
    monkeypatch.setattr(servy, "_is_administrator", lambda: True)
    calls: list[list[str]] = []
    contents = '{"Name": "BellhopRig1"}'

    def run_export(args, **kwargs):
        calls.append(args)
        Path(args[args.index("--path") + 1]).write_text(contents, encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="")

    monkeypatch.setattr(subprocess, "run", run_export)
    cli_app(
        [
            "service",
            "export-servy-config",
            "--servy-cli",
            str(fake_servy_cli),
            "--name",
            "BellhopRig1",
        ],
        result_action="print_non_none_return_zero",
    )

    assert capsys.readouterr().out.strip() == contents
    assert len(calls) == 1
    assert calls[0][:7] == [
        str(fake_servy_cli),
        "export",
        "--name",
        "BellhopRig1",
        "--config",
        "json",
        "--path",
    ]
    temporary_path = Path(calls[0][7])
    assert temporary_path.name == "servy-export.json"
    assert not temporary_path.parent.exists()


def test_export_to_file_option(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_servy_cli = tmp_path / "servy-cli.exe"
    fake_servy_cli.write_text("stub")
    destination = tmp_path / "new-folder" / "config.yaml"
    monkeypatch.setattr(servy, "_is_administrator", lambda: True)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: calls.append(args) or subprocess.CompletedProcess(args, 0, stdout=""),
    )

    result = cli_app(
        [
            "service",
            "export-servy-config",
            "--servy-cli",
            str(fake_servy_cli),
            "--file",
            str(destination),
            "--config",
            "yaml",
        ],
        result_action="return_value",
    )

    assert result == destination
    assert destination.parent.is_dir()
    assert calls == [
        [str(fake_servy_cli), "export", "--name", "Bellhop", "--config", "yaml", "--path", str(destination)]
    ]


@pytest.mark.parametrize("command", ["start", "stop", "restart", "uninstall", "show", "export-servy-config"])
def test_service_commands_require_administrator(
    command: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(servy, "_is_administrator", lambda: False)

    with pytest.raises(SystemExit) as exc:
        cli_app(["service", command], result_action="return_value")

    assert exc.value.code == 1
    assert "Administrator privileges are required" in capsys.readouterr().err


def test_servy_command_reports_subprocess_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    fake_servy_cli = tmp_path / "servy-cli.exe"
    fake_servy_cli.write_text("stub")
    monkeypatch.setattr(servy, "_is_administrator", lambda: False)

    def fail(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr="service unavailable")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        status(servy_cli=fake_servy_cli)

    assert "service unavailable" in capsys.readouterr().err


def test_export_cleans_up_temporary_directory_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_servy_cli = tmp_path / "servy-cli.exe"
    fake_servy_cli.write_text("stub")
    monkeypatch.setattr(servy, "_is_administrator", lambda: True)
    paths: list[Path] = []

    def fail(args, **kwargs):
        paths.append(Path(args[args.index("--path") + 1]))
        raise subprocess.CalledProcessError(1, args, stderr="export failed")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        export_servy_config(servy_cli=fake_servy_cli)

    assert len(paths) == 1
    assert not paths[0].parent.exists()


def test_servy_version_and_ui_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    fake_servy_cli = tmp_path / "servy-cli.exe"
    monkeypatch.setattr(servy, "_resolve_servy_cli", lambda servy_cli=None: fake_servy_cli)
    calls: list[list[str | Path]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: calls.append(args) or subprocess.CompletedProcess(args, 0, stdout="Servy output\n"),
    )

    cli_app(["service", "servy-version"], result_action="return_value")
    cli_app(["service", "ui"], result_action="return_value")

    assert calls == [
        [str(fake_servy_cli), "version", "--name", DEFAULT_SERVICE_NAME],
        [tmp_path / "Servy.Manager.exe"],
    ]
    assert capsys.readouterr().out == "Servy output\nServy output\n"

from __future__ import annotations

import itertools
import subprocess
import sys
import time
from multiprocessing import Process, Queue
from pathlib import Path
from queue import Empty

import pytest
from bellhop_models.specifications import RunCommandParams, RunProgramParams
from cyclopts import App

from bellhop.subprocess_utils import run_live_process
from bellhop.task_executors import _run_command


def _drain(log_queue: Queue[str], timeout: float = 2.0) -> list[str]:
    # Queue.empty() is unreliable (the feeder thread may not have flushed yet),
    # so block briefly on get() and stop only once nothing more arrives.
    lines = []
    while True:
        try:
            lines.append(log_queue.get(timeout=timeout))
        except Empty:
            break
    return lines


# Define a simple dummy process to use in tests
app = App()


@app.command()
def dummy_process(lifetime: int = 3, exit_code: int = 0):
    for n in range(lifetime):
        time.sleep(1)
        print(f"Message {n + 1}")
    return exit_code


## tests


@pytest.mark.parametrize(
    "params",
    [
        # Shell commands (RunCommandParams, shell=True, verbatim): builtins work without cmd /c
        RunCommandParams(command="whoami"),
        RunCommandParams(command="hostname"),
        RunCommandParams(command='echo "Hello, World!"'),
        RunCommandParams(command='dir /b "C:\\Windows"'),
        # Forward-slash quoted path survives verbatim through the shell
        RunCommandParams(command='dir /b "C:/Program Files"'),
        # cwd honored by the child process
        RunCommandParams(command="dir /b", cwd=Path("C:/Windows")),
        # Programs run directly (RunProgramParams, shell=False, explicit argv)
        RunProgramParams(program=sys.executable, arguments=[__file__, "dummy_process", "--lifetime", "1"]),
        RunProgramParams(
            program=sys.executable,
            arguments=[Path(__file__).name, "dummy_process", "--lifetime", "1"],
            cwd=Path(__file__).parent,
        ),
    ],
)
def test_commands(params: RunCommandParams | RunProgramParams):
    log_queue: Queue[str] = Queue()
    _run_command(params, log_queue)


def test_command_output():
    marker = "BELLHOP_MARKER_42"
    command = RunCommandParams(command=f"echo {marker}")
    log_queue: Queue[str] = Queue()
    _run_command(command, log_queue)

    output = _drain(log_queue)
    assert any(marker in line for line in output)


def test_run_command_handles_list():
    markers = ["MARKER_ONE", "MARKER_TWO"]
    command = RunCommandParams(command=[f"echo {m}" for m in markers])
    log_queue: Queue[str] = Queue()
    _run_command(command, log_queue)

    output = _drain(log_queue)
    assert all(any(m in line for line in output) for m in markers)


def test_run_program_executes():
    marker = "PROGRAM_MARKER"
    params = RunProgramParams(program=sys.executable, arguments=["-c", f"print('{marker}')"])
    log_queue: Queue[str] = Queue()
    _run_command(params, log_queue)
    assert any(marker in line for line in _drain(log_queue))


def test_program_args_isolated():
    # In no-shell (program) mode each list item is one argv entry; spaces are not re-split.
    code = "import sys; print(sys.argv[1])"
    command = [sys.executable, "-c", code, "a b c"]
    log_queue: Queue[str] = Queue()
    run_live_process(command, log_queue, shell=False)
    output = "\n".join(_drain(log_queue))
    assert output.strip() == "a b c"


def test_live_process_nonzero_exit_raises():
    command = [sys.executable, __file__, "dummy_process", "--lifetime", "0", "--exit-code", "1"]
    log_queue: Queue[str] = Queue()
    with pytest.raises(subprocess.CalledProcessError):
        run_live_process(command, log_queue, shell=False)


def test_command_honors_cwd(tmp_path):
    log_queue: Queue[str] = Queue()
    run_live_process("cd", log_queue, shell=True, cwd=tmp_path)
    output = "\n".join(_drain(log_queue))
    assert output.strip().lower() == str(tmp_path).lower()


def test_live_command_output():
    command = [sys.executable, __file__, "dummy_process", "--lifetime", "3", "--exit-code", "0"]
    log_queue: Queue[str] = Queue()
    process = Process(target=run_live_process, args=(command, log_queue, False))
    process.start()

    output = []
    while True:
        while not log_queue.empty():
            output.append((time.time(), log_queue.get()))
        if not process.is_alive() and log_queue.empty():
            break
    times = [t for t, msg in output if "Message" in msg]
    deltas = [t2 - t1 for t1, t2 in itertools.pairwise(times)]
    assert all(0.9 <= delta <= 1.1 for delta in deltas)


if __name__ == "__main__":
    app()

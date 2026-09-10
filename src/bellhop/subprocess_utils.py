from __future__ import annotations

import os
import subprocess
from multiprocessing import Queue


def run_subprocess(program: str, command: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run([program] + command, capture_output=True, text=True)
    proc.check_returncode()
    return proc


def run_live_process(program: str, command: list[str], log_queue: Queue[str]) -> None:
    process = subprocess.Popen(
        [program] + command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=os.environ | {"PYTHONUNBUFFERED": "1"},
        shell=True,
    )
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            log_queue.put(line.rstrip())
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, program)

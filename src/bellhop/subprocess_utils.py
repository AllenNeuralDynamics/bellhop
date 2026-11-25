from __future__ import annotations

import os
import subprocess
from multiprocessing import Queue
from pathlib import Path

# # --- Splitting a Windows Command String Safely ---
# def _windows_split(cmd_line) -> list[str]:
#     """Split a command-line string into an argv list using the real Windows parser.

#     Windows does not tokenize command lines the way POSIX shells do: backslashes
#     and double quotes follow MSVCRT ``argv`` rules (e.g. backslashes are only
#     escapes when they precede a quote). ``shlex.split`` cannot reproduce these
#     rules, so a naive split corrupts paths like ``C:\\Users\\foo`` and mishandles
#     quoted arguments. This delegates to ``CommandLineToArgvW`` -- the same shell32
#     API that Windows itself uses to build ``argv`` -- guaranteeing identical,
#     correct handling of backslashes and quotes.
#     """
#     # Call the native Windows API
#     CommandLineToArgvW = ctypes.windll.shell32.CommandLineToArgvW
#     CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
#     CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)

#     lp_argc = ctypes.c_int()
#     ptr = CommandLineToArgvW(cmd_line, ctypes.byref(lp_argc))
#     if not ptr:
#         raise ValueError("Failed to parse command line.")

#     args = [ptr[i] for i in range(lp_argc.value)]
#     ctypes.windll.kernel32.LocalFree(ptr)
#     return args


# def _split_command(command: str) -> list[str]:
#     if os.name == "nt":
#         return _windows_split(command)
#     else:
#         return shlex.split(command)


def run_live_process(command: str | list[str], log_queue: Queue[str], shell: bool, cwd: Path | None = None) -> None:
    """Run a single command, streaming its combined stdout/stderr into ``log_queue``.

    ``command`` is passed to ``Popen`` as-is: with ``shell=True`` a ``str`` runs
    verbatim through the shell; with ``shell=False`` a ``list[str]`` is an explicit
    argv run directly with no shell parsing.
    """
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=os.environ | {"PYTHONUNBUFFERED": "1"},
        cwd=cwd,
        shell=shell,
    )
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            log_queue.put(line.rstrip())
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command)

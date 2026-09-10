import time

from cyclopts import App

from bellhop.subprocess_utils import run_live_process

app = App()


@app.command()
def dummy_process(lifetime: int = 3, exit_code: int = 0):
    for n in range(lifetime):
        time.sleep(1)
        print(f"Message {n + 1}")
    return exit_code


@app.command()
def test_run_live_process():
    lifetime = 3
    return_code = 0
    command = [
        "uv",
        "run",
        __file__,
        "dummy_process",
        "--lifetime",
        str(lifetime),
        "--exit-code",
        str(return_code),
    ]
    output, result = run_live_process(command[0], command[1:])

    print(output)
    # assert result == return_code


if __name__ == "__main__":
    app()

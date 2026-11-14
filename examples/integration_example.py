"""
Bellhop integration examples covering the main use cases:

  1. Success       — multi-task job runs to completion with live logs
  2. Failure       — task raises an error, job halts and stores the message
  3. Update        — job rescheduled before it fires via execute_now
  4. Retry         — failed job is reset and re-run
  5. Abort         — long-running job is hard-killed mid-execution

Run with:  uv run python examples/integration_example.py
"""

import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from bellhop_models.database import TaskExecution
from bellhop_models.specifications import JobSpecification, RunSubprocessParams, SubprocessTask

from bellhop.engine import Engine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECTION = "\n" + "=" * 60 + "\n"


def _wait_for_start(engine: Engine, job_id) -> None:
    while True:
        job = engine.db.get_job(job_id)
        if job and job.state != "Not Started":
            return
        time.sleep(0.1)


def _wait_for_terminal(engine: Engine, job_id, timeout=20) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = engine.db.get_job(job_id)
        if job and job.state in ("Completed", "Errored"):
            return job.state
        time.sleep(0.1)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")


def _watch_execution(engine: Engine, execution_id) -> TaskExecution:
    sent_length = 0
    while True:
        execution = engine.db.get_execution(execution_id)
        new = execution.logs[sent_length:]
        if new:
            for line in new.split("\n"):
                if line:
                    print(f"    {line}", flush=True)
            sent_length += len(new)
        if execution.success is not None:
            return execution
        time.sleep(0.05)


def _watch_job(engine: Engine, job_id) -> str:
    _wait_for_start(engine, job_id)
    seen = set()
    while True:
        job = engine.db.get_job(job_id)
        active = next((e for e in job.history if e.success is None), None)
        if active is not None and active.id not in seen:
            seen.add(active.id)
            idx = next(i for i, t in enumerate(job.tasks) if t.id == active.task.id)
            print(f"\n[{idx + 1}/{len(job.tasks)}] {active.task.name}")
            execution = _watch_execution(engine, active.id)
            status = "✓" if execution.success else "✗"
            detail = "" if execution.success else f": {execution.message}"
            print(f"{status} {active.task.name}{detail}")
        if job.state in ("Completed", "Errored"):
            print(f"\nJob {job.state}.")
            return job.state
        time.sleep(0.05)


def _python_in_subprocess(name: str, script: str) -> SubprocessTask:
    return SubprocessTask(
        name=name,
        parameters=RunSubprocessParams(program=sys.executable, command=["-c", script]),
    )


# ---------------------------------------------------------------------------
# 1. Success
# ---------------------------------------------------------------------------


def example_success(engine: Engine) -> None:
    print(SECTION + "1. SUCCESS — multi-task job")
    spec = JobSpecification(
        name="Success Example",
        tasks=[
            _python_in_subprocess(
                "Count to three",
                "import time\nfor i in range(1, 4):\n    print(f'  step {i}/3', flush=True)\n    time.sleep(0.2)\n",
            ),
            _python_in_subprocess("Say goodbye", "print('  Goodbye!', flush=True)"),
        ],
        time_scheduled=datetime.now(),
    )
    job_id = engine.submit_job(spec)
    _watch_job(engine, job_id)


# ---------------------------------------------------------------------------
# 2. Failure
# ---------------------------------------------------------------------------


def example_failure(engine: Engine) -> None:
    print(SECTION + "2. FAILURE — task raises an error")
    spec = JobSpecification(
        name="Failure Example",
        tasks=[
            _python_in_subprocess("Will fail", "raise RuntimeError('something went wrong')"),
            _python_in_subprocess("Should not run", "print('this should not appear')"),
        ],
        time_scheduled=datetime.now(),
    )
    job_id = engine.submit_job(spec)
    _watch_job(engine, job_id)
    job = engine.db.get_job(job_id)
    print(f"Tasks run: {sum(1 for t in job.tasks if t.state != 'Not Started')}/{len(job.tasks)}")


# ---------------------------------------------------------------------------
# 3. Update (reschedule to now)
# ---------------------------------------------------------------------------


def example_update_schedule(engine: Engine) -> None:
    print(SECTION + "3. UPDATE — reschedule a pending job to run immediately")
    spec = JobSpecification(
        name="Update Example",
        tasks=[_python_in_subprocess("Quick task", "print('  ran immediately', flush=True)")],
        time_scheduled=datetime.now() + timedelta(hours=1),
    )
    job_id = engine.submit_job(spec)
    print("Submitted, originally scheduled for +1 hour. Rescheduling now...")
    engine.execute_now(job_id)
    _watch_job(engine, job_id)


# ---------------------------------------------------------------------------
# 4. Retry
# ---------------------------------------------------------------------------


def example_retry(engine: Engine) -> None:
    print(SECTION + "4. RETRY — fail, fix, retry")
    with tempfile.TemporaryDirectory() as tmp:
        flag = Path(tmp) / "ready.flag"
        # Script fails until the flag file exists
        script = (
            f"from pathlib import Path\n"
            f"flag = Path(r'{flag}')\n"
            f"if not flag.exists():\n"
            f"    raise RuntimeError('not ready yet')\n"
            f"print('  flag found, succeeding', flush=True)\n"
        )
        spec = JobSpecification(
            name="Retry Example",
            tasks=[_python_in_subprocess("Check flag", script)],
            time_scheduled=datetime.now(),
        )
        job_id = engine.submit_job(spec)
        _watch_job(engine, job_id)

        print("\nCreating flag file and retrying...")
        flag.touch()
        engine.retry_job(job_id)
        _watch_job(engine, job_id)


# ---------------------------------------------------------------------------
# 5. Abort
# ---------------------------------------------------------------------------


def example_abort(engine: Engine) -> None:
    print(SECTION + "5. ABORT — kill a long-running job")
    spec = JobSpecification(
        name="Abort Example",
        tasks=[
            _python_in_subprocess(
                "Long running task",
                "import time\nfor i in range(60):\n    print(f'  tick {i}', flush=True)\n    time.sleep(0.5)\n",
            )
        ],
        time_scheduled=datetime.now(),
    )
    job_id = engine.submit_job(spec)
    _wait_for_start(engine, job_id)
    time.sleep(1.5)  # let it print a few ticks
    print(f"\nAborting job {job_id}...")
    engine.abort_job(job_id)
    job = engine.db.get_job(job_id)
    print(f"Job state after abort: {job.state}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    engine = Engine().start()
    try:
        example_success(engine)
        example_failure(engine)
        example_update_schedule(engine)
        example_retry(engine)
        example_abort(engine)
    finally:
        engine.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

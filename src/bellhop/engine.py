import datetime
import multiprocessing
import sys
import threading
import uuid

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler
from bellhop_models.database import Job, Task, TaskExecution
from bellhop_models.specifications import JobSpecification
from loguru import logger

from bellhop.db import DATABASE_FILE, Database
from bellhop.task_executors import task_executor_registry


class Engine:
    def __init__(self, db_file: str = DATABASE_FILE):
        self._db = Database(db_file)
        # never skip a job as "misfired"; late jobs should still run rather than being dropped
        self._scheduler = BackgroundScheduler(job_defaults={"misfire_grace_time": None})
        self._running_executors: dict[uuid.UUID, JobExecutor] = {}
        self._lock = threading.Lock()  # protects _running_executors

    @property
    def db(self) -> Database:
        return self._db

    def start(self) -> "Engine":
        self._scheduler.start()
        self._reschedule_pending_jobs()
        return self

    def _reschedule_pending_jobs(self) -> None:
        """Re-add jobs left in the DB as 'Not Started' (e.g. after a restart) to the scheduler."""
        for job in self._db.query_jobs(state_list=["Not Started"]):
            logger.info(f"Rescheduling pending job '{job.name}' ({job.id})")
            self._scheduler.add_job(
                self._launch_job,
                args=[job],
                id=str(job.id),
                trigger="date",
                run_date=job.next_execution_time,
            )

    def shutdown(self) -> None:
        self._scheduler.shutdown()

    def submit_job(self, job_spec: JobSpecification) -> uuid.UUID:
        job = Job.from_specification(job_spec)
        self._db.create_job(job)
        logger.info(f"Job '{job.name}' submitted, scheduled for {job.next_execution_time}")
        self._scheduler.add_job(
            self._launch_job,
            args=[job],
            id=str(job.id),
            trigger="date",
            run_date=job.next_execution_time,
        )
        return job.id

    def update_job(self, job: Job) -> None:
        self._db.update_job(job)
        try:
            self._scheduler.modify_job(str(job.id), args=[job])
            self._scheduler.reschedule_job(str(job.id), trigger="date", run_date=job.next_execution_time)
        except JobLookupError:
            pass  # job already fired or is currently executing

    def execute_now(self, job_id: uuid.UUID) -> None:
        job = self._db.get_job(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        now = datetime.datetime.now()
        self._scheduler.reschedule_job(str(job_id), trigger="date", run_date=now)
        job.next_execution_time = now
        self._db.update_job(job)

    def retry_job(self, job_id: uuid.UUID) -> None:
        job = self._db.get_job(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        job.state = "Not Started"
        job.next_task = 0
        job.next_execution_time = datetime.datetime.now()
        self._db.update_job(job)
        try:
            self._scheduler.modify_job(str(job_id), args=[job])
            self._scheduler.reschedule_job(str(job_id), trigger="date", run_date=job.next_execution_time)
        except JobLookupError:
            self._scheduler.add_job(
                self._launch_job,
                args=[job],
                id=str(job.id),
                trigger="date",
                run_date=job.next_execution_time,
            )

    def abort_job(self, job_id: uuid.UUID) -> None:
        with self._lock:
            executor = self._running_executors.pop(job_id, None)
        if executor is not None:
            executor.kill()
            logger.info(f"Job {job_id} killed")
        try:
            self._scheduler.remove_job(str(job_id))
        except JobLookupError:
            pass
        job = self._db.get_job(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        job.state = "Errored"
        self._db.update_job(job)

    def _launch_job(self, job: Job) -> None:
        logger.info(f"Launching job '{job.name}' ({job.id})")
        with self._lock:
            dead = [jid for jid, ex in self._running_executors.items() if not ex.is_alive()]
            for jid in dead:
                self._running_executors.pop(jid)
            executor = JobExecutor(job, self._db._db_file)
            self._running_executors[job.id] = executor
        executor.start()


## Execution


class JobExecutor:
    def __init__(self, job: Job, db_file: str):
        self.job = job
        self._process = multiprocessing.Process(
            target=_execute_job, args=(job.id, db_file), daemon=True, name=f"job-{job.id}"
        )

    def start(self) -> None:
        self._process.start()

    def kill(self) -> None:
        if self._process is not None and self._process.is_alive():
            self._process.kill()

    def is_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()


def _execute_job(job_id: uuid.UUID, db_file: str) -> None:
    logger.remove()
    logger.add(sys.stderr)
    database = Database(db_file)
    job = database.get_job(job_id)
    if job is None:
        return
    logger.info(f"Job '{job.name}' ({job_id}) starting")
    job.state = "In Progress"
    database.update_job(job)

    while job.next_task is not None:
        task = job.tasks[job.next_task]
        logger.info(f"Starting task '{task.name}' [{job.next_task + 1}/{len(job.tasks)}]")
        task.state = "In Progress"
        database.update_task(task)

        task_execution = _execute_task(task, database)  # blocking; process.kill() stops it here

        if task_execution.success:
            logger.info(f"Task '{task.name}' completed")
            task.state = "Completed"
            database.update_task(task)
            if job.next_task == len(job.tasks) - 1:
                job.next_task = None
                job.state = "Completed"
            else:
                job.next_task += 1
                job.state = "In Progress"
            database.update_job(job)
        else:
            task.state = "Errored"
            database.update_task(task)
            job.state = "Errored"
            logger.error(f"Task '{task.name}' failed: {task_execution.message}")
            database.update_job(job)
            return


class _LogWriter:
    """Appends log lines to a TaskExecution record in the DB as they arrive."""

    def __init__(self, execution_id: uuid.UUID, database: Database):
        self._execution_id = execution_id
        self._db = database
        self._lines: list[str] = []

    def put(self, line: str) -> None:
        self._lines.append(line)
        self._db._update_execution_logs(self._execution_id, "\n".join(self._lines))

    @property
    def all_logs(self) -> str:
        return "\n".join(self._lines)


def _execute_task(task: Task, database: Database) -> TaskExecution:
    execution = TaskExecution(task=task, time_started=datetime.datetime.now())
    database.add_execution(execution)
    log_writer = _LogWriter(execution.id, database)
    message = None
    try:
        task_executor_registry[task.task_type](task.parameters, log_writer)
        success = True
    except Exception as e:
        success = False
        message = repr(e)
    execution.success = success
    execution.message = message
    execution.time_ended = datetime.datetime.now()
    execution.logs = log_writer.all_logs
    database.update_execution(execution)
    return execution

import queue
import uuid
from typing import Self

import httpx
from bellhop_models.database import Job, JobSummary, TaskExecution
from bellhop_models.specifications import JobSpecification

BASE_URL = "http://localhost:8312"


class BellhopClient:
    def __init__(self, base_url: str = BASE_URL, client: httpx.Client | None = None):
        self._client = client or httpx.Client(base_url=base_url)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def health_check(self) -> dict[str, str]:
        return self._client.get("/").raise_for_status().json()

    def get_environment(self) -> dict[str, str]:
        return self._client.get("/environment").raise_for_status().json()

    def list_jobs(self) -> list[JobSummary]:
        response = self._client.get("/jobs")
        return [JobSummary.model_validate(item) for item in response.raise_for_status().json()]

    def submit_job(self, job_spec: JobSpecification) -> uuid.UUID:
        response = self._client.post("/jobs", json=job_spec.model_dump(mode="json"))
        return uuid.UUID(response.raise_for_status().json())

    def get_job(self, job_id: uuid.UUID) -> Job:
        response = self._client.get(f"/jobs/{job_id}")
        return Job.model_validate(response.raise_for_status().json())

    def update_job(self, job_id: uuid.UUID, job: Job) -> None:
        if job.id != job_id:
            raise ValueError("Body job ID must match path job ID")
        self._client.put(f"/jobs/{job_id}", json=job.model_dump(mode="json")).raise_for_status()

    def abort_job(self, job_id: uuid.UUID) -> None:
        self._client.delete(f"/jobs/{job_id}").raise_for_status()

    def execute_now(self, job_id: uuid.UUID) -> None:
        self._client.post(f"/jobs/{job_id}/execute-now").raise_for_status()

    def retry_job(self, job_id: uuid.UUID) -> None:
        self._client.post(f"/jobs/{job_id}/retry").raise_for_status()

    def get_execution(self, execution_id: uuid.UUID) -> TaskExecution:
        response = self._client.get(f"/executions/{execution_id}")
        return TaskExecution.model_validate(response.raise_for_status().json())

    def stream_execution_logs(self, execution_id: uuid.UUID, result_queue: queue.Queue | None = None) -> str:
        """Stream live logs for a running task execution as Server-Sent Events."""
        result = ""
        with self._client.stream("GET", f"/executions/{execution_id}/logs") as response:
            response.raise_for_status()
            for line in response.iter_text():
                if result_queue is not None:
                    result_queue.put(line)
                result += line
        return result


class AsyncBellhopClient:
    def __init__(self, base_url: str = BASE_URL, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(base_url=base_url)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def health_check(self) -> dict[str, str]:
        response = await self._client.get("/")
        print(response, response.text)
        return response.raise_for_status().json()

    async def get_environment(self) -> dict[str, str]:
        return (await self._client.get("/environment")).raise_for_status().json()

    async def list_jobs(self) -> list[JobSummary]:
        response = await self._client.get("/jobs")
        return [JobSummary.model_validate(item) for item in response.raise_for_status().json()]

    async def submit_job(self, job_spec: JobSpecification) -> uuid.UUID:
        response = await self._client.post("/jobs", json=job_spec.model_dump(mode="json"))
        return uuid.UUID(response.raise_for_status().json())

    async def get_job(self, job_id: uuid.UUID) -> Job:
        response = await self._client.get(f"/jobs/{job_id}")
        return Job.model_validate(response.raise_for_status().json())

    async def update_job(self, job_id: uuid.UUID, job: Job) -> None:
        if job.id != job_id:
            raise ValueError("Body job ID must match path job ID")
        response = await self._client.put(f"/jobs/{job_id}", json=job.model_dump(mode="json"))
        response.raise_for_status()

    async def abort_job(self, job_id: uuid.UUID) -> None:
        (await self._client.delete(f"/jobs/{job_id}")).raise_for_status()

    async def execute_now(self, job_id: uuid.UUID) -> None:
        (await self._client.post(f"/jobs/{job_id}/execute-now")).raise_for_status()

    async def retry_job(self, job_id: uuid.UUID) -> None:
        (await self._client.post(f"/jobs/{job_id}/retry")).raise_for_status()

    async def get_execution(self, execution_id: uuid.UUID) -> TaskExecution:
        response = await self._client.get(f"/executions/{execution_id}")
        return TaskExecution.model_validate(response.raise_for_status().json())

    async def stream_execution_logs(self, execution_id: uuid.UUID, result_queue: queue.Queue | None = None) -> str:
        """Stream live logs for a running task execution as Server-Sent Events."""
        result = ""
        async with self._client.stream("GET", f"/executions/{execution_id}/logs") as response:
            response.raise_for_status()
            async for line in response.aiter_text():
                if result_queue is not None:
                    result_queue.put(line)
                result += line
        return result


def health_check() -> dict[str, str]:
    with BellhopClient() as client:
        return client.health_check()


def get_environment() -> dict[str, str]:
    with BellhopClient() as client:
        return client.get_environment()


def list_jobs() -> list[JobSummary]:
    with BellhopClient() as client:
        return client.list_jobs()


def submit_job(job_spec: JobSpecification) -> uuid.UUID:
    with BellhopClient() as client:
        return client.submit_job(job_spec)


def submit_job_safe(job_spec: JobSpecification) -> uuid.UUID:
    try:
        return submit_job(job_spec)
    except Exception:  # TODO: Catch exceptions only if the server isn't running
        # serialize job_spec and write to a file in the dropbox
        pass


def get_job(job_id: uuid.UUID) -> Job:
    with BellhopClient() as client:
        return client.get_job(job_id)


def update_job(job_id: uuid.UUID, job: Job) -> None:
    with BellhopClient() as client:
        client.update_job(job_id, job)


def abort_job(job_id: uuid.UUID) -> None:
    with BellhopClient() as client:
        client.abort_job(job_id)


def execute_now(job_id: uuid.UUID) -> None:
    with BellhopClient() as client:
        client.execute_now(job_id)


def retry_job(job_id: uuid.UUID) -> None:
    with BellhopClient() as client:
        client.retry_job(job_id)


def get_execution(execution_id: uuid.UUID) -> TaskExecution:
    with BellhopClient() as client:
        return client.get_execution(execution_id)


def stream_execution_logs(execution_id: uuid.UUID, result_queue: queue.Queue | None = None) -> str:
    with BellhopClient() as client:
        return client.stream_execution_logs(execution_id, result_queue)

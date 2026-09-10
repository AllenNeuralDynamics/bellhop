import asyncio
import uuid

import httpx
import pytest
from bellhop_models.database import Job
from bellhop_models.specifications import JobSpecification, RunSubprocessParams, SubprocessTask

from bellhop_client.client import AsyncBellhopClient, BellhopClient


def make_job() -> Job:
    return Job.from_specification(
        JobSpecification(
            name="Test job",
            tasks=[SubprocessTask(name="Echo", parameters=RunSubprocessParams(program="echo", command=[]))],
        )
    )


def make_transport(job: Job) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/jobs" and request.method == "GET":
            return httpx.Response(200, json=[job.model_dump(mode="json")])
        if request.url.path == "/jobs" and request.method == "POST":
            return httpx.Response(201, json=str(job.id))
        return httpx.Response(204)

    return httpx.MockTransport(handler)


def test_sync_client_lists_jobs_and_handles_empty_mutation_responses():
    job = make_job()
    client = BellhopClient(client=httpx.Client(base_url="http://test", transport=make_transport(job)))

    jobs = client.list_jobs()
    assert [(result.id, result.name) for result in jobs] == [(job.id, job.name)]
    client.abort_job(job.id)
    client.execute_now(job.id)
    client.retry_job(job.id)


def test_async_client_lists_jobs_and_handles_empty_mutation_responses():
    async def run_test():
        job = make_job()
        http_client = httpx.AsyncClient(base_url="http://test", transport=make_transport(job))
        client = AsyncBellhopClient(client=http_client)

        jobs = await client.list_jobs()
        assert [(result.id, result.name) for result in jobs] == [(job.id, job.name)]
        await client.abort_job(job.id)
        await client.execute_now(job.id)
        await client.retry_job(job.id)
        await http_client.aclose()

    asyncio.run(run_test())


def test_client_rejects_mismatched_job_id():
    job = make_job()
    other_id = uuid.uuid4()
    client = BellhopClient(client=httpx.Client(base_url="http://test", transport=make_transport(job)))

    with pytest.raises(ValueError, match="Body job ID must match path job ID"):
        client.update_job(other_id, job)

"""Hand-written client boilerplate shared by the generated clients.

The generated ``BellhopClient`` / ``AsyncBellhopClient`` classes inherit these
bases for construction, lifecycle, and the streaming endpoint (which can't be
expressed as a simple request/response and so is not generated).
"""

import queue
import uuid
from typing import Self

import httpx

BASE_URL = "http://localhost:8312"


class SyncClientBase:
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


class AsyncClientBase:
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

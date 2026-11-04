import logging

from bellhop_client import AsyncBellhopClient


class ClientRegistry:
    """Out-of-state registry mapping session IDs to AsyncBellhopClient instances.
    Reflex can't keep non-pickleable objects in state, so this way we can have separate
    client instances per UI session."""

    _clients: dict[str, AsyncBellhopClient] = {}

    @classmethod
    def get_client(cls, session_id: str, base_url: str) -> AsyncBellhopClient:
        # Create a new client if one doesn't exist for this session
        if session_id not in cls._clients:
            cls._clients[session_id] = AsyncBellhopClient(base_url=base_url)
        return cls._clients[session_id]

    @classmethod
    async def update_client(cls, session_id: str, base_url: str) -> AsyncBellhopClient:
        """Re-instantiates client when base_url or auth changes, closing the old one."""
        await cls._close(cls._clients.pop(session_id, None))
        new_client = AsyncBellhopClient(base_url=base_url)
        cls._clients[session_id] = new_client
        return new_client

    @classmethod
    async def remove_client(cls, session_id: str) -> None:
        await cls._close(cls._clients.pop(session_id, None))

    @staticmethod
    async def _close(client: AsyncBellhopClient | None) -> None:
        if client is None:
            return
        try:
            await client.aclose()
        except Exception:
            logging.exception("failed to close API client")

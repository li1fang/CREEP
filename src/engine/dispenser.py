"""Redis-backed Dispenser that hands asset IDs to workers."""

from typing import Optional


class Dispenser:
    """Pops queued asset IDs from Redis for workers to process."""

    def __init__(self, redis_client, queue_name: str = "creep:assets", timeout: int = 5) -> None:
        self.redis_client = redis_client
        self.queue_name = queue_name
        self.timeout = timeout

    def acquire(self) -> Optional[str]:
        """Blockingly pop an asset ID from Redis.

        Returns ``None`` on timeout.
        """

        result = self.redis_client.blpop(self.queue_name, timeout=self.timeout)
        if result is None:
            return None

        _queue, raw_value = result
        if isinstance(raw_value, bytes):
            return raw_value.decode()

        return str(raw_value)

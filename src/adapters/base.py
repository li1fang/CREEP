"""Adapter interface for vendor integrations."""
from __future__ import annotations

import abc
import asyncio
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Optional, Protocol, TypedDict


class AdapterError(Exception):
    """Base exception for adapter-related failures."""


class ResourceUnavailableError(AdapterError):
    """Raised when the upstream provider cannot deliver the requested resource."""


class QuotaExceededError(AdapterError):
    """Raised when the upstream provider enforces a rate limit or quota violation."""


class HealthStatus(TypedDict, total=False):
    """Represents the availability of a provisioned asset."""

    asset_id: str
    status: str  # expected values: "healthy", "degraded", "unhealthy"
    detail: Optional[str]
    checked_at: datetime


class CostModel(TypedDict, total=False):
    """Describes how the adapter accrues cost for usage."""

    model: str  # e.g. "per_request", "per_hour", "flat"
    unit_cost: float
    currency: str
    notes: Optional[str]


class ResourcePayload(TypedDict, total=False):
    """Payload returned by an adapter when a resource is acquired."""

    asset_id: str
    credentials: MutableMapping[str, Any]
    metadata: MutableMapping[str, Any]


class SyncAdapter(Protocol):
    """Protocol for synchronous adapter implementations."""

    def acquire(self, specs: Mapping[str, Any]) -> ResourcePayload:
        ...

    def release(self, asset_id: str) -> bool:
        ...

    def check_health(self, asset_id: str) -> HealthStatus:
        ...

    @property
    def cost_model(self) -> CostModel:
        ...


class BaseAdapter(abc.ABC):
    """Defines the contract for all vendor adapters."""

    def __init__(self, config: Optional[Mapping[str, Any]] = None) -> None:
        self.config: Mapping[str, Any] = config or {}

    @abc.abstractmethod
    def acquire(self, specs: Mapping[str, Any]) -> ResourcePayload:
        """Provision or fetch a resource from the upstream provider."""

    @abc.abstractmethod
    def release(self, asset_id: str) -> bool:
        """Return or tear down a resource at the upstream provider."""

    @abc.abstractmethod
    def check_health(self, asset_id: str) -> HealthStatus:
        """Validate that a resource remains usable."""

    @property
    @abc.abstractmethod
    def cost_model(self) -> CostModel:
        """Return the billing metadata for this adapter."""

    async def acquire_async(self, specs: Mapping[str, Any]) -> ResourcePayload:
        """Asynchronous wrapper around :meth:`acquire`."""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.acquire, specs)

    async def release_async(self, asset_id: str) -> bool:
        """Asynchronous wrapper around :meth:`release`."""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.release, asset_id)

    async def check_health_async(self, asset_id: str) -> HealthStatus:
        """Asynchronous wrapper around :meth:`check_health`."""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.check_health, asset_id)

    def _health_status(self, asset_id: str, status: str, detail: Optional[str] = None) -> HealthStatus:
        """Helper to build a timestamped health status payload."""

        return {
            "asset_id": asset_id,
            "status": status,
            "detail": detail,
            "checked_at": datetime.now(timezone.utc),
        }

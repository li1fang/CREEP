"""Mock adapter simulating real-world provider behavior."""
from __future__ import annotations

import random
import time
from typing import Any, Mapping, MutableMapping

from .base import (
    BaseAdapter,
    CostModel,
    HealthStatus,
    QuotaExceededError,
    ResourcePayload,
    ResourceUnavailableError,
)


class MockAdapter(BaseAdapter):
    """A mock adapter used for local development and CI."""

    DEFAULT_LATENCY_MS = 150.0
    DEFAULT_LATENCY_JITTER_MS = 100.0
    DEFAULT_RATE_LIMIT_PROBABILITY = 0.05
    DEFAULT_PROVIDER_ERROR_PROBABILITY = 0.02

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(config)
        self.rng = rng or random.Random()
        self.latency_ms = float(self.config.get("latency_ms", self.DEFAULT_LATENCY_MS))
        self.latency_jitter_ms = float(
            self.config.get("latency_jitter_ms", self.DEFAULT_LATENCY_JITTER_MS)
        )
        self.rate_limit_probability = float(
            self.config.get("rate_limit_probability", self.DEFAULT_RATE_LIMIT_PROBABILITY)
        )
        self.provider_error_probability = float(
            self.config.get(
                "provider_error_probability", self.DEFAULT_PROVIDER_ERROR_PROBABILITY
            )
        )
        self._cost_model: CostModel = {
            "model": self.config.get("cost_model", "per_request"),
            "unit_cost": float(self.config.get("unit_cost", 0.0)),
            "currency": self.config.get("currency", "USD"),
            "notes": "Mock adapter incurs no real cost.",
        }

    def _simulate_latency(self) -> None:
        jitter = self.rng.uniform(-self.latency_jitter_ms, self.latency_jitter_ms)
        total_ms = max(0.0, self.latency_ms + jitter)
        time.sleep(total_ms / 1000.0)

    def _maybe_raise_failure(self) -> None:
        roll = self.rng.random()
        if roll < self.rate_limit_probability:
            raise QuotaExceededError("Rate limit encountered during mock request")
        if roll < self.rate_limit_probability + self.provider_error_probability:
            raise ResourceUnavailableError("Provider error encountered during mock request")

    def acquire(self, specs: Mapping[str, Any]) -> ResourcePayload:
        self._simulate_latency()
        self._maybe_raise_failure()
        payload: ResourcePayload = {
            "asset_id": str(specs.get("asset_id") or self.rng.randint(1, 1_000_000)),
            "credentials": self._build_credentials(specs),
            "metadata": {"specs": dict(specs)},
        }
        return payload

    def release(self, asset_id: str) -> bool:
        self._simulate_latency()
        self._maybe_raise_failure()
        return True

    def check_health(self, asset_id: str) -> HealthStatus:
        self._simulate_latency()
        self._maybe_raise_failure()
        return self._health_status(asset_id=asset_id, status="healthy")

    @property
    def cost_model(self) -> CostModel:
        return self._cost_model

    def _build_credentials(self, specs: Mapping[str, Any]) -> MutableMapping[str, Any]:
        credentials: MutableMapping[str, Any] = {
            "token": specs.get("token", f"mock-token-{self.rng.randint(1000, 9999)}"),
            "endpoint": specs.get("endpoint", "https://mock.vendor.local"),
        }
        return credentials

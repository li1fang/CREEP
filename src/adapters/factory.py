"""Factory for loading vendor adapters."""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Type

from .base import BaseAdapter
from .mock_vendor import MockAdapter
from src.config import load_prefixed_env


class AdapterFactory:
    """Factory to instantiate adapters by name."""

    _REGISTRY: MutableMapping[str, Type[BaseAdapter]] = {
        "mock": MockAdapter,
    }

    @classmethod
    def register(cls, name: str, adapter_cls: Type[BaseAdapter]) -> None:
        cls._REGISTRY[name] = adapter_cls

    @classmethod
    def create(cls, name: str, config: Mapping[str, Any] | None = None) -> BaseAdapter:
        adapter_cls = cls._REGISTRY.get(name)
        if adapter_cls is None:
            raise ValueError(f"Adapter '{name}' is not registered")

        adapter_config = cls._load_config(name)
        merged_config = {**adapter_config, **(config or {})}
        return adapter_cls(merged_config)

    @staticmethod
    def _load_config(name: str) -> Mapping[str, Any]:
        """Load adapter-specific config from the environment."""

        prefix = f"ADAPTER_{name.upper()}_"
        return load_prefixed_env(prefix)

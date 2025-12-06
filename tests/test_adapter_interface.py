import unittest

from src.adapters.base import BaseAdapter, QuotaExceededError, ResourceUnavailableError
from src.adapters.mock_vendor import MockAdapter


class AdapterInterfaceTests(unittest.TestCase):
    def test_mock_adapter_complies_with_base(self):
        adapter: BaseAdapter = MockAdapter({
            "latency_ms": 0,
            "latency_jitter_ms": 0,
            "rate_limit_probability": 0,
            "provider_error_probability": 0,
        })

        payload = adapter.acquire({"asset_id": "asset-123", "token": "token"})
        self.assertEqual(payload["asset_id"], "asset-123")
        self.assertIn("credentials", payload)
        self.assertIn("metadata", payload)

        health = adapter.check_health(payload["asset_id"])
        self.assertEqual(health["status"], "healthy")

        self.assertTrue(adapter.release(payload["asset_id"]))
        self.assertIn("model", adapter.cost_model)

    def test_mock_adapter_simulates_failures(self):
        adapter = MockAdapter({
            "latency_ms": 0,
            "latency_jitter_ms": 0,
            "rate_limit_probability": 1.0,
            "provider_error_probability": 0,
        })

        with self.assertRaises(QuotaExceededError):
            adapter.acquire({})

        adapter = MockAdapter({
            "latency_ms": 0,
            "latency_jitter_ms": 0,
            "rate_limit_probability": 0,
            "provider_error_probability": 1.0,
        })

        with self.assertRaises(ResourceUnavailableError):
            adapter.check_health("asset-1")


if __name__ == "__main__":
    unittest.main()

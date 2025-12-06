import json
import unittest
from unittest.mock import MagicMock

from src.adapters.base import BaseAdapter
from src.engine.worker import Worker


class WorkerTaskAwareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cursor_mock = MagicMock()
        self.cursor_mock.__enter__.return_value = self.cursor_mock
        self.cursor_mock.__exit__.return_value = None
        self.db_mock = MagicMock()
        self.db_mock.cursor.return_value = self.cursor_mock
        self.db_mock.commit = MagicMock()
        self.db_mock.rollback = MagicMock()

        self.dispenser_mock = MagicMock()
        self.adapter_mock = MagicMock(spec=BaseAdapter)
        self.adapter_mock.acquire.return_value = {
            "asset_id": "asset-1",
            "credentials": {},
            "metadata": {},
        }
        self.adapter_mock.check_health.return_value = {"status": "healthy", "asset_id": "asset-1"}
        self.adapter_mock.release.return_value = True

    def _build_payload(self, task_id: str, lease_ids):
        return json.dumps({"task_id": task_id, "lease_ids": lease_ids})

    def test_ticket_sniper_successful_settlement(self):
        worker = Worker(self.dispenser_mock, self.db_mock, adapter=self.adapter_mock)

        self.cursor_mock.fetchone.return_value = ("TICKET_SNIPER", 1000)
        self.cursor_mock.fetchall.return_value = [
            ("lease-1", "task-1", "asset-1", "tenant-1", "project-1", {}),
            ("lease-2", "task-1", "asset-2", "tenant-1", "project-1", {}),
        ]

        payload = self._build_payload("task-1", ["lease-1", "lease-2"])

        worker._process_one(payload)

        self.cursor_mock.execute.assert_any_call(
            Worker.SELECT_TASK_SQL, ("task-1",)
        )
        self.cursor_mock.execute.assert_any_call(
            Worker.SELECT_LEASES_SQL, (["lease-1", "lease-2"],)
        )
        self.cursor_mock.execute.assert_any_call(
            Worker.UPDATE_TASK_SUCCESS_SQL, ("task-1",)
        )
        self.cursor_mock.execute.assert_any_call(
            Worker.UPDATE_LEASE_SUCCESS_SQL, (["lease-1", "lease-2"],)
        )
        self.cursor_mock.execute.assert_any_call(
            Worker.UPDATE_ASSET_COOLING_SQL, (["asset-1", "asset-2"],)
        )
        self.db_mock.commit.assert_called()

    def test_invalid_lease_marks_task_failed(self):
        worker = Worker(self.dispenser_mock, self.db_mock, adapter=self.adapter_mock)

        self.cursor_mock.fetchone.return_value = ("TICKET_SNIPER", 1000)
        self.cursor_mock.fetchall.return_value = []

        payload = self._build_payload("task-1", ["missing-lease"])

        worker._process_one(payload)

        self.cursor_mock.execute.assert_any_call(
            Worker.UPDATE_TASK_FAILURE_SQL, ("RESOURCE_ERROR", "task-1")
        )
        self.cursor_mock.execute.assert_any_call(
            Worker.UPDATE_LEASE_FAILURE_SQL, (["missing-lease"],)
        )
        self.db_mock.commit.assert_called()

    def test_missing_lease_detected_as_data_inconsistency(self):
        worker = Worker(self.dispenser_mock, self.db_mock, adapter=self.adapter_mock)

        self.cursor_mock.fetchone.return_value = ("TICKET_SNIPER", 1000)
        self.cursor_mock.fetchall.return_value = [
            ("lease-1", "task-1", "asset-1", "tenant-1", "project-1", {}),
        ]

        payload = self._build_payload("task-1", ["lease-1", "lease-2"])

        worker._process_one(payload)

        self.cursor_mock.execute.assert_any_call(
            Worker.UPDATE_TASK_FAILURE_SQL, ("DATA_INCONSISTENCY", "task-1")
        )
        self.cursor_mock.execute.assert_any_call(
            Worker.UPDATE_LEASE_FAILURE_SQL, (["lease-1", "lease-2"],)
        )
        self.db_mock.commit.assert_called()


if __name__ == "__main__":
    unittest.main()

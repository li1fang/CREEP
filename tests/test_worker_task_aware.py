import json
import random
import unittest
from unittest.mock import MagicMock, patch

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

    def _build_payload(self, task_id: str, lease_ids):
        return json.dumps({"task_id": task_id, "lease_ids": lease_ids})

    @patch("time.sleep", return_value=None)
    @patch.object(random, "random", return_value=0.4)
    def test_ticket_sniper_successful_settlement(self, random_mock, sleep_mock):
        worker = Worker(self.dispenser_mock, self.db_mock)

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

    @patch("time.sleep", return_value=None)
    def test_invalid_lease_marks_task_failed(self, sleep_mock):
        worker = Worker(self.dispenser_mock, self.db_mock)

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

    @patch("time.sleep", return_value=None)
    def test_missing_lease_detected_as_data_inconsistency(self, sleep_mock):
        worker = Worker(self.dispenser_mock, self.db_mock)

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

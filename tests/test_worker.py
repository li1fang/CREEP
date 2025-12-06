import random
import unittest
from unittest.mock import MagicMock, patch

from src.engine.worker import Worker


class WorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cursor_mock = MagicMock()
        self.cursor_mock.__enter__.return_value = self.cursor_mock
        self.cursor_mock.__exit__.return_value = None
        self.db_mock = MagicMock()
        self.db_mock.cursor.return_value = self.cursor_mock
        self.db_mock.commit = MagicMock()
        self.db_mock.rollback = MagicMock()
        self.cursor_mock.fetchone.return_value = ("tenant-1", "project-1")

        self.dispenser_mock = MagicMock()

    @patch("time.sleep", return_value=None)
    @patch.object(random, "random", return_value=0.1)
    def test_success_flow_updates_asset_and_records_entries(self, random_mock, sleep_mock):
        worker = Worker(self.dispenser_mock, self.db_mock)

        worker._process_one("asset-1")

        self.cursor_mock.execute.assert_any_call(Worker.UPDATE_SUCCESS_SQL, ("asset-1",))
        self.cursor_mock.execute.assert_any_call(
            Worker.INSERT_EVENT_SQL, ("asset-1", "TASK_SUCCESS", "INFO", None)
        )
        self.cursor_mock.execute.assert_any_call(
            Worker.INSERT_LEDGER_SQL,
            ("asset-1", "tenant-1", "project-1", "OUT", "TASK_BURN", 0.01),
        )
        self.db_mock.commit.assert_called_once()

    @patch("time.sleep", return_value=None)
    @patch.object(random, "random", return_value=0.9)
    def test_failure_flow_bans_asset(self, random_mock, sleep_mock):
        worker = Worker(self.dispenser_mock, self.db_mock)

        worker._process_one("asset-2")

        self.cursor_mock.execute.assert_any_call(Worker.UPDATE_FAILURE_SQL, ("asset-2",))
        self.cursor_mock.execute.assert_any_call(
            Worker.INSERT_EVENT_SQL, ("asset-2", "TASK_FAIL", "ERROR", "MOCK_FAIL")
        )
        self.cursor_mock.execute.assert_any_call(
            Worker.INSERT_LEDGER_SQL,
            ("asset-2", "tenant-1", "project-1", "OUT", "TASK_BURN", 0.01),
        )
        self.db_mock.commit.assert_called_once()

    @patch("time.sleep", return_value=None)
    def test_idle_when_queue_empty(self, sleep_mock):
        self.dispenser_mock.acquire.side_effect = [None, KeyboardInterrupt()]
        worker = Worker(self.dispenser_mock, self.db_mock)

        with self.assertRaises(KeyboardInterrupt):
            worker.run_forever()

        sleep_mock.assert_called_with(worker.POLL_INTERVAL)


if __name__ == "__main__":
    unittest.main()

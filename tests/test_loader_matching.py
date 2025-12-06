import json
import unittest
from unittest.mock import MagicMock

from src.engine.loader import Loader


class LoaderMatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.redis_mock = MagicMock()

        self.cursor_mock = MagicMock()
        self.cursor_mock.__enter__.return_value = self.cursor_mock
        self.cursor_mock.__exit__.return_value = None

        self.db_mock = MagicMock()
        self.db_mock.cursor.return_value = self.cursor_mock
        self.db_mock.commit = MagicMock()
        self.db_mock.rollback = MagicMock()

    def test_matches_assets_by_attributes_and_queues_payload(self):
        task_row = [
            (
                "task-uk",
                "tenant-1",
                json.dumps([{"sku_category": "RAW_NET", "attributes": {"geo": "UK"}}]),
                5000,
            )
        ]

        candidate_assets = [
            ("asset-us", "RAW_NET", "ip.us", {"geo": "US"}),
            ("asset-uk", "RAW_NET", "ip.uk", {"geo": "UK"}),
        ]

        locked_assets = [("asset-uk", "RAW_NET", "ip.uk", {"geo": "UK"})]

        lease_rows = [("lease-1",)]

        self.cursor_mock.fetchall.side_effect = [
            task_row,
            candidate_assets,
            locked_assets,
        ]
        self.cursor_mock.fetchone.side_effect = lease_rows

        loader = Loader(self.db_mock, self.redis_mock, queue_name="creep:test")
        payloads = loader.sync()

        self.cursor_mock.execute.assert_any_call(Loader.CLAIM_PENDING_TASKS_SQL, (1,))
        self.cursor_mock.execute.assert_any_call(
            Loader.SELECT_CANDIDATE_ASSETS_SQL, ("RAW_NET", None, None)
        )
        self.cursor_mock.execute.assert_any_call(
            f"{Loader.LOCK_ASSETS_SQL} LIMIT %s", ("RAW_NET", None, None, 1)
        )
        self.cursor_mock.execute.assert_any_call(
            Loader.UPDATE_ASSET_STATUS_SQL, (["asset-uk"],)
        )
        self.cursor_mock.execute.assert_any_call(Loader.UPDATE_TASK_STATUS_SQL, ("task-uk",))

        self.db_mock.commit.assert_called_once()
        self.redis_mock.rpush.assert_called_once()

        payload = json.loads(payloads[0])
        self.assertEqual("task-uk", payload["task_id"])
        self.assertEqual(["lease-1"], payload["lease_ids"])

    def test_skips_task_when_assets_unavailable(self):
        task_row = [
            (
                "task-missing",
                "tenant-1",
                json.dumps([{"sku_category": "RAW_NET", "attributes": {"geo": "CA"}}]),
                5000,
            )
        ]

        self.cursor_mock.fetchall.side_effect = [task_row, []]

        loader = Loader(self.db_mock, self.redis_mock)
        payloads = loader.sync()

        self.cursor_mock.execute.assert_any_call(Loader.CLAIM_PENDING_TASKS_SQL, (1,))
        self.db_mock.rollback.assert_called_once()
        self.redis_mock.rpush.assert_not_called()
        self.assertEqual([], payloads)


if __name__ == "__main__":
    unittest.main()

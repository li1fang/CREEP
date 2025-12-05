import unittest
from unittest.mock import MagicMock

from src.engine import Dispenser, Loader


class LoaderDispenserIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.redis_mock = MagicMock()

        self.cursor_mock = MagicMock()
        self.cursor_mock.__enter__.return_value = self.cursor_mock
        self.cursor_mock.__exit__.return_value = None

        self.db_mock = MagicMock()
        self.db_mock.cursor.return_value = self.cursor_mock
        self.db_mock.commit = MagicMock()
        self.db_mock.rollback = MagicMock()

    def test_loader_moves_ready_assets_and_updates_status(self):
        self.cursor_mock.fetchall.return_value = [("asset-1",), ("asset-2",)]

        # Ensure commit occurs before Redis publish
        def rpush_side_effect(*args, **kwargs):
            self.assertTrue(self.db_mock.commit.called)

        self.redis_mock.rpush.side_effect = rpush_side_effect

        loader = Loader(self.db_mock, self.redis_mock, queue_name="creep:test")
        asset_ids = loader.sync()

        self.cursor_mock.execute.assert_any_call(Loader.SELECT_READY_SQL)
        self.cursor_mock.execute.assert_any_call(Loader.UPDATE_STATUS_SQL, (["asset-1", "asset-2"],))
        self.db_mock.commit.assert_called_once()
        self.redis_mock.rpush.assert_called_once_with("creep:test", "asset-1", "asset-2")
        self.assertEqual(["asset-1", "asset-2"], asset_ids)

    def test_loader_skips_when_no_ready_assets(self):
        self.cursor_mock.fetchall.return_value = []

        loader = Loader(self.db_mock, self.redis_mock)
        asset_ids = loader.sync()

        self.cursor_mock.execute.assert_called_once_with(Loader.SELECT_READY_SQL)
        self.redis_mock.rpush.assert_not_called()
        self.db_mock.rollback.assert_called_once()
        self.assertEqual([], asset_ids)

    def test_loader_rolls_back_on_errors(self):
        self.cursor_mock.fetchall.side_effect = RuntimeError("db error")

        loader = Loader(self.db_mock, self.redis_mock)
        with self.assertRaises(RuntimeError):
            loader.sync()

        self.db_mock.rollback.assert_called()

    def test_dispenser_blocks_and_decodes(self):
        redis_client = MagicMock()
        redis_client.blpop.return_value = ("creep:assets", b"asset-99")

        dispenser = Dispenser(redis_client, queue_name="creep:assets", timeout=1)
        asset_id = dispenser.acquire()

        redis_client.blpop.assert_called_once_with("creep:assets", timeout=1)
        self.assertEqual("asset-99", asset_id)


if __name__ == "__main__":
    unittest.main()

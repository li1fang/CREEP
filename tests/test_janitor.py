import unittest
from unittest.mock import MagicMock

from src.engine import Janitor


class JanitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cursor_mock = MagicMock()
        self.cursor_mock.__enter__.return_value = self.cursor_mock
        self.cursor_mock.__exit__.return_value = None

        self.db_mock = MagicMock()
        self.db_mock.cursor.return_value = self.cursor_mock
        self.db_mock.commit = MagicMock()
        self.db_mock.rollback = MagicMock()

    def test_recovers_expired_locks(self):
        self.cursor_mock.fetchall.return_value = [("asset-1",)]

        janitor = Janitor(self.db_mock)
        recovered = janitor.recover_timeouts()

        self.cursor_mock.execute.assert_any_call(
            Janitor.SELECT_EXPIRED_LOCKS_SQL, (Janitor.BATCH_SIZE,)
        )
        self.cursor_mock.execute.assert_any_call(Janitor.RECOVER_LOCKS_SQL, (["asset-1"],))
        self.cursor_mock.execute.assert_any_call(
            Janitor.INSERT_EVENT_SQL, ("asset-1", "LOCK_TIMEOUT_RECOVERY")
        )
        self.db_mock.commit.assert_called_once()
        self.assertEqual(["asset-1"], recovered)

    def test_ignores_cooling_assets_with_future_timestamp(self):
        self.cursor_mock.fetchall.return_value = []

        janitor = Janitor(self.db_mock)
        cooled = janitor.process_cooling()

        self.cursor_mock.execute.assert_called_once_with(
            Janitor.SELECT_EXPIRED_COOLING_SQL, (Janitor.BATCH_SIZE,)
        )
        self.db_mock.rollback.assert_called_once()
        self.assertEqual([], cooled)

    def test_skip_locked_prevents_double_processing(self):
        # Simulate two sequential janitor runs pulling the same query; SKIP LOCKED ensures
        # the second run receives no rows.
        self.cursor_mock.fetchall.side_effect = [[("asset-1",)], []]

        janitor = Janitor(self.db_mock)
        first_batch = janitor.recover_timeouts()
        second_batch = janitor.recover_timeouts()

        self.assertEqual(["asset-1"], first_batch)
        self.assertEqual([], second_batch)
        select_calls = [call for call in self.cursor_mock.execute.call_args_list if call[0][0] == Janitor.SELECT_EXPIRED_LOCKS_SQL]
        self.assertEqual(2, len(select_calls))
        update_calls = [call for call in self.cursor_mock.execute.call_args_list if call[0][0] == Janitor.RECOVER_LOCKS_SQL]
        self.assertEqual(1, len(update_calls))


if __name__ == "__main__":
    unittest.main()

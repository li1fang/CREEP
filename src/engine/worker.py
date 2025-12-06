"""Worker service that consumes assets from Redis and finalizes execution state."""

import random
import time
from typing import Optional


class Worker:
    """Single-threaded worker that executes queued assets."""

    POLL_INTERVAL = 1

    SELECT_ASSET_SQL = "SELECT tenant_id, project_id FROM creep_assets WHERE id=%s"
    UPDATE_SUCCESS_SQL = (
        "UPDATE creep_assets SET status='COOLING', cool_down_until = CURRENT_TIMESTAMP + INTERVAL '10 seconds' "
        "WHERE id=%s"
    )
    UPDATE_FAILURE_SQL = "UPDATE creep_assets SET status='BANNED', health_score = health_score - 10 WHERE id=%s"
    INSERT_EVENT_SQL = (
        "INSERT INTO asset_events (asset_id, event_type, severity, error_code, occurred_at, recorded_at) "
        "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    INSERT_LEDGER_SQL = (
        "INSERT INTO asset_ledger (asset_id, tenant_id, project_id, direction, reason, amount, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)"
    )

    def __init__(self, dispenser, db_conn) -> None:
        self.dispenser = dispenser
        self.db_conn = db_conn

    def run_forever(self) -> None:
        """Continuously process assets from the queue."""

        while True:
            asset_id = self.dispenser.acquire()
            if asset_id is None:
                time.sleep(self.POLL_INTERVAL)
                continue

            self._process_one(asset_id)

    def _process_one(self, asset_id: str) -> None:
        """Process a single asset through the mock execution lifecycle."""

        tenant_id, project_id = self._load_asset_context(asset_id)

        # Simulate execution duration
        time.sleep(0.1)
        success = random.random() < 0.8

        try:
            with self.db_conn.cursor() as cursor:
                if success:
                    cursor.execute(self.UPDATE_SUCCESS_SQL, (asset_id,))
                    cursor.execute(
                        self.INSERT_EVENT_SQL,
                        (asset_id, "TASK_SUCCESS", "INFO", None),
                    )
                    cursor.execute(
                        self.INSERT_LEDGER_SQL,
                        (asset_id, tenant_id, project_id, "OUT", "TASK_BURN", 0.01),
                    )
                else:
                    cursor.execute(self.UPDATE_FAILURE_SQL, (asset_id,))
                    cursor.execute(
                        self.INSERT_EVENT_SQL,
                        (asset_id, "TASK_FAIL", "ERROR", "MOCK_FAIL"),
                    )
                    cursor.execute(
                        self.INSERT_LEDGER_SQL,
                        (asset_id, tenant_id, project_id, "OUT", "TASK_BURN", 0.01),
                    )

            self.db_conn.commit()
        except Exception:
            self.db_conn.rollback()
            raise

    def _load_asset_context(self, asset_id: str) -> tuple:
        """Fetch tenant and project identifiers for the asset."""

        with self.db_conn.cursor() as cursor:
            cursor.execute(self.SELECT_ASSET_SQL, (asset_id,))
            row: Optional[tuple] = cursor.fetchone()

        if row is None:
            raise ValueError(f"Asset {asset_id} not found")

        tenant_id, project_id = row
        return tenant_id, project_id

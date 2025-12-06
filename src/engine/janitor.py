"""Background reconciliation loops for asset lifecycle transitions."""

from typing import List, Sequence

from src.config import settings


class Janitor:
    """Reconciles stuck assets and cooling assets back into the READY pool."""

    BATCH_SIZE = settings.janitor_batch_size
    MAX_PROCESS_LIMIT = settings.janitor_max_process_limit

    SELECT_EXPIRED_LOCKS_SQL = (
        "SELECT id FROM creep_assets "
        "WHERE status='LOCKED' AND lock_expires_at < CURRENT_TIMESTAMP "
        "FOR UPDATE SKIP LOCKED LIMIT %s"
    )
    RECOVER_LOCKS_SQL = (
        "UPDATE creep_assets "
        "SET status='READY', lock_id=NULL, lock_expires_at=NULL, fail_count=COALESCE(fail_count, 0) + 1 "
        "WHERE id = ANY(%s)"
    )

    SELECT_EXPIRED_COOLING_SQL = (
        "SELECT id FROM creep_assets "
        "WHERE status='COOLING' AND cool_down_until < CURRENT_TIMESTAMP "
        "FOR UPDATE SKIP LOCKED LIMIT %s"
    )
    RECOVER_COOLING_SQL = "UPDATE creep_assets SET status='READY', cool_down_until=NULL WHERE id = ANY(%s)"

    INSERT_EVENT_SQL = (
        "INSERT INTO asset_events (asset_id, event_type, occurred_at, recorded_at) "
        "VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    def __init__(self, db_conn) -> None:
        self.db_conn = db_conn

    def run_once(self) -> None:
        """Execute one pass of each reconciliation routine."""

        self.recover_timeouts()
        self.process_cooling()

    def recover_timeouts(self) -> List[str]:
        """Release assets whose locks have expired."""

        processed_count = 0
        recovered_assets: List[str] = []

        try:
            with self.db_conn.cursor() as cursor:
                while processed_count < self.MAX_PROCESS_LIMIT:
                    cursor.execute(self.SELECT_EXPIRED_LOCKS_SQL, (self.BATCH_SIZE,))
                    rows: Sequence[Sequence[str]] = cursor.fetchall()
                    asset_ids = [row[0] for row in rows]

                    if not asset_ids:
                        self.db_conn.rollback()
                        return recovered_assets

                    cursor.execute(self.RECOVER_LOCKS_SQL, (asset_ids,))
                    for asset_id in asset_ids:
                        cursor.execute(self.INSERT_EVENT_SQL, (asset_id, "LOCK_TIMEOUT_RECOVERY"))

                    recovered_assets.extend(asset_ids)
                    processed_count += len(asset_ids)
                    self.db_conn.commit()

                    if len(asset_ids) < self.BATCH_SIZE or processed_count >= self.MAX_PROCESS_LIMIT:
                        return recovered_assets
        except Exception:
            self.db_conn.rollback()
            raise

    def process_cooling(self) -> List[str]:
        """Return cooled assets to the READY pool."""

        processed_count = 0
        cooled_assets: List[str] = []

        try:
            with self.db_conn.cursor() as cursor:
                while processed_count < self.MAX_PROCESS_LIMIT:
                    cursor.execute(self.SELECT_EXPIRED_COOLING_SQL, (self.BATCH_SIZE,))
                    rows: Sequence[Sequence[str]] = cursor.fetchall()
                    asset_ids = [row[0] for row in rows]

                    if not asset_ids:
                        self.db_conn.rollback()
                        return cooled_assets

                    cursor.execute(self.RECOVER_COOLING_SQL, (asset_ids,))
                    for asset_id in asset_ids:
                        cursor.execute(self.INSERT_EVENT_SQL, (asset_id, "COOLING_ENDED"))

                    cooled_assets.extend(asset_ids)
                    processed_count += len(asset_ids)
                    self.db_conn.commit()

                    if len(asset_ids) < self.BATCH_SIZE or processed_count >= self.MAX_PROCESS_LIMIT:
                        return cooled_assets
        except Exception:
            self.db_conn.rollback()
            raise

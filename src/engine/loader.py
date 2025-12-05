"""Loader that moves ready assets from Postgres into Redis queues."""

from typing import List, Sequence


class Loader:
    """Hydrates a Redis queue with ready assets from PostgreSQL."""

    SELECT_READY_SQL = (
        "SELECT id FROM creep_assets "
        "WHERE status='READY' "
        "FOR UPDATE SKIP LOCKED LIMIT 100"
    )
    UPDATE_STATUS_SQL = "UPDATE creep_assets SET status='LOCKED' WHERE id = ANY(%s)"

    def __init__(self, db_conn, redis_client, queue_name: str = "creep:assets") -> None:
        self.db_conn = db_conn
        self.redis_client = redis_client
        self.queue_name = queue_name

    def sync(self) -> List[str]:
        """Lock ready assets in Postgres, then enqueue them in Redis.

        Database changes are committed *before* publishing to Redis to prevent
        double-enqueue in failure scenarios. Assets that fail to enqueue remain
        LOCKED for a janitor to reconcile.
        """

        try:
            with self.db_conn.cursor() as cursor:
                cursor.execute(self.SELECT_READY_SQL)
                rows: Sequence[Sequence[str]] = cursor.fetchall()
                asset_ids = [row[0] for row in rows]

                if not asset_ids:
                    self.db_conn.rollback()
                    return []

                cursor.execute(self.UPDATE_STATUS_SQL, (asset_ids,))

            # Commit the status change before emitting to Redis to avoid
            # double-publishing in the event of DB errors.
            self.db_conn.commit()

            # Push to a Redis list so workers can block-pop items in order.
            self.redis_client.rpush(self.queue_name, *asset_ids)

            return asset_ids
        except Exception:
            self.db_conn.rollback()
            raise

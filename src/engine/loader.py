"""Loader that binds TaskOrders to assets and enqueues leases."""

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Sequence


class Loader:
    """Hydrates a Redis queue with task-aware lease payloads."""

    BATCH_SIZE = 1

    CLAIM_PENDING_TASKS_SQL = (
        "SELECT task_id, tenant_id, resource_hints, timeout_ms "
        "FROM task_orders "
        "WHERE status='PENDING' "
        "ORDER BY priority DESC, created_at ASC "
        "FOR UPDATE SKIP LOCKED "
        "LIMIT %s"
    )

    LOCK_MATCHING_ASSETS_SQL = (
        "SELECT id, sku_category, sku_code, meta_spec "
        "FROM creep_assets "
        "WHERE status='READY' "
        "AND sku_category=%s "
        "AND (%s IS NULL OR sku_code LIKE %s) "
        "AND meta_spec @> %s::jsonb "
        "LIMIT %s "
        "FOR UPDATE SKIP LOCKED"
    )

    UPDATE_ASSET_STATUS_SQL = "UPDATE creep_assets SET status='LOCKED' WHERE id = ANY(%s)"

    INSERT_LEASE_SQL = (
        "INSERT INTO leases (tenant_id, task_id, asset_id, expires_at, status) "
        "VALUES (%s, %s, %s, %s, 'ACTIVE') RETURNING lease_id"
    )

    UPDATE_TASK_STATUS_SQL = "UPDATE task_orders SET status='QUEUED' WHERE task_id=%s"

    def __init__(self, db_conn, redis_client, queue_name: str = "creep:tasks") -> None:
        self.db_conn = db_conn
        self.redis_client = redis_client
        self.queue_name = queue_name

    def sync(self) -> List[str]:
        """Lock assets for pending tasks, create leases, and enqueue payloads."""

        try:
            with self.db_conn.cursor() as cursor:
                tasks = self._claim_tasks(cursor)
                if not tasks:
                    self.db_conn.rollback()
                    return []

                task_id, tenant_id, resource_hints, timeout_ms = tasks[0]
                parsed_hints = self._parse_hints(resource_hints)

                matching_assets = self._lock_assets_for_hints(
                    cursor, tenant_id, parsed_hints
                )
                if not matching_assets:
                    self.db_conn.rollback()
                    return []

                lease_ids = self._insert_leases(cursor, tenant_id, task_id, timeout_ms, matching_assets)
                cursor.execute(self.UPDATE_TASK_STATUS_SQL, (task_id,))

            self.db_conn.commit()

            payload = json.dumps({"task_id": task_id, "lease_ids": lease_ids})
            self.redis_client.rpush(self.queue_name, payload)

            return [payload]
        except Exception:
            self.db_conn.rollback()
            raise

    def _claim_tasks(self, cursor) -> Sequence[Sequence]:
        cursor.execute(self.CLAIM_PENDING_TASKS_SQL, (self.BATCH_SIZE,))
        return cursor.fetchall()

    def _parse_hints(self, raw_hints) -> List[Dict]:
        if isinstance(raw_hints, str):
            return json.loads(raw_hints)
        return list(raw_hints or [])

    def _lock_assets_for_hints(self, cursor, tenant_id: str, hints: List[Dict]) -> List[Dict]:
        selected_assets: List[Dict] = []
        for hint in hints:
            sku_category = hint.get("sku_category")
            sku_code = hint.get("sku_code")
            attributes = hint.get("attributes", {})
            min_count = int(hint.get("min_count", 1))

            if not sku_category:
                return []

            locked = self._lock_candidates(cursor, sku_category, sku_code, attributes, min_count)
            if len(locked) < min_count:
                return []

            asset_ids = [asset[0] for asset in locked]
            cursor.execute(self.UPDATE_ASSET_STATUS_SQL, (asset_ids,))

            for asset_id, locked_category, locked_code, locked_attrs in locked:
                selected_assets.append(
                    {
                        "asset_id": asset_id,
                        "sku_category": locked_category,
                        "sku_code": locked_code,
                        "attributes": locked_attrs,
                    }
                )

        return selected_assets

    def _lock_candidates(
        self, cursor, sku_category: str, sku_code: str, attributes: Dict[str, str], limit: int
    ) -> List[Sequence]:
        like_pattern = self._to_like_pattern(sku_code)
        attributes_json = json.dumps(attributes or {})
        cursor.execute(
            self.LOCK_MATCHING_ASSETS_SQL,
            (sku_category, sku_code, like_pattern, attributes_json, limit),
        )
        rows = cursor.fetchall()
        return rows

    def _insert_leases(
        self,
        cursor,
        tenant_id: str,
        task_id: str,
        timeout_ms: int,
        assets: List[Dict],
    ) -> List[str]:
        lease_ids: List[str] = []
        expires_at = datetime.now(timezone.utc) + timedelta(milliseconds=int(timeout_ms or 0))
        for asset in assets:
            cursor.execute(
                self.INSERT_LEASE_SQL,
                (tenant_id, task_id, asset["asset_id"], expires_at),
            )
            lease_row = cursor.fetchone()
            lease_ids.append(lease_row[0])

        return lease_ids

    def _to_like_pattern(self, sku_code: str) -> str:
        if sku_code is None:
            return sku_code
        return sku_code.replace("*", "%")

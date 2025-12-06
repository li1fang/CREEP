"""Worker service that consumes task payloads from Redis and finalizes execution."""

import json
import logging
import time
from typing import Dict, List, Optional

from src.adapters.base import AdapterError, BaseAdapter
from src.adapters.factory import AdapterFactory
from src.config import settings


LOGGER = logging.getLogger(__name__)


class Worker:
    """Single-threaded worker that executes queued tasks."""

    POLL_INTERVAL = settings.worker_poll_interval
    MOCK_SUCCESS_RATE = settings.worker_mock_success_rate

    SELECT_TASK_SQL = "SELECT task_type, timeout_ms FROM task_orders WHERE task_id=%s"
    SELECT_LEASES_SQL = (
        "SELECT l.lease_id, l.task_id, l.asset_id, a.tenant_id, a.project_id, a.meta_spec "
        "FROM leases l "
        "JOIN creep_assets a ON l.asset_id = a.id "
        "WHERE l.lease_id = ANY(%s)"
    )
    UPDATE_TASK_SUCCESS_SQL = (
        "UPDATE task_orders SET status='SUCCESS', finished_at=CURRENT_TIMESTAMP, result_code=NULL WHERE task_id=%s"
    )
    UPDATE_TASK_FAILURE_SQL = (
        "UPDATE task_orders SET status='FAILED', finished_at=CURRENT_TIMESTAMP, result_code=%s WHERE task_id=%s"
    )
    UPDATE_LEASE_SUCCESS_SQL = "UPDATE leases SET status='RELEASED' WHERE lease_id = ANY(%s)"
    UPDATE_LEASE_FAILURE_SQL = "UPDATE leases SET status='REVOKED' WHERE lease_id = ANY(%s)"
    UPDATE_ASSET_COOLING_SQL = (
        "UPDATE creep_assets SET status='COOLING', cool_down_until = CURRENT_TIMESTAMP + INTERVAL '10 seconds' "
        "WHERE id = ANY(%s)"
    )
    UPDATE_ASSET_FAILURE_SQL = "UPDATE creep_assets SET status='BANNED' WHERE id = ANY(%s)"
    INSERT_EVENT_SQL = (
        "INSERT INTO asset_events (asset_id, event_type, severity, error_code, occurred_at, recorded_at) "
        "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    INSERT_LEDGER_SQL = (
        "INSERT INTO asset_ledger (asset_id, tenant_id, project_id, direction, reason, amount, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)"
    )

    def __init__(
        self,
        dispenser,
        db_conn,
        adapter: Optional[BaseAdapter] = None,
        adapter_name: str = "mock",
        adapter_config: Optional[Dict] = None,
    ) -> None:
        self.dispenser = dispenser
        self.db_conn = db_conn
        self.adapter = adapter or AdapterFactory.create(adapter_name, adapter_config)

    def run_forever(self) -> None:
        """Continuously process task payloads from the queue."""

        while True:
            payload = self.dispenser.acquire()
            if payload is None:
                time.sleep(self.POLL_INTERVAL)
                continue

            self._process_one(payload)

    def _process_one(self, payload: str) -> None:
        """Process a single task order and settle the related leases."""

        parsed = self._parse_payload(payload)
        if parsed is None:
            return

        task_id = parsed.get("task_id")
        lease_ids = parsed.get("lease_ids") or []
        if not task_id:
            LOGGER.error("Received payload without task_id: %s", payload)
            return

        try:
            with self.db_conn.cursor() as cursor:
                task_row = self._fetch_task(cursor, task_id)
                if task_row is None:
                    LOGGER.critical(
                        "Task %s not found during hydration. Dropping payload.", task_id
                    )
                    self.db_conn.rollback()
                    return

                leases = self._fetch_leases(cursor, lease_ids)

            missing_leases = set(lease_ids) - {lease["lease_id"] for lease in leases}
            invalid_task_link = any(lease["task_id"] != task_id for lease in leases)
            missing_assets = any(lease.get("asset_id") is None for lease in leases)

            if missing_assets or invalid_task_link or missing_leases:
                result_code = "DATA_INCONSISTENCY" if leases else "RESOURCE_ERROR"
                with self.db_conn.cursor() as cursor:
                    if missing_leases:
                        LOGGER.critical(
                            "Missing leases for task %s: %s", task_id, sorted(missing_leases)
                        )
                    if missing_assets:
                        LOGGER.critical("Missing assets for task %s", task_id)
                    if invalid_task_link:
                        LOGGER.critical("Lease/task mismatch detected for task %s", task_id)
                    self._settle_failure(
                        cursor, task_id, leases, result_code, lease_ids
                    )
                self.db_conn.commit()
                return

            task_type, _timeout_ms = task_row
            success = self._execute_task(task_type, leases)

            with self.db_conn.cursor() as cursor:
                if success:
                    self._settle_success(cursor, task_id, leases)
                else:
                    self._settle_failure(cursor, task_id, leases, "EXECUTION_FAILED", lease_ids)

            self.db_conn.commit()
        except Exception:
            self.db_conn.rollback()
            raise

    def _parse_payload(self, payload: str) -> Optional[Dict]:
        try:
            if isinstance(payload, bytes):
                payload = payload.decode()
            return json.loads(payload)
        except Exception:
            LOGGER.error("Unable to parse payload: %s", payload)
            return None

    def _fetch_task(self, cursor, task_id: str) -> Optional[tuple]:
        cursor.execute(self.SELECT_TASK_SQL, (task_id,))
        return cursor.fetchone()

    def _fetch_leases(self, cursor, lease_ids: List[str]) -> List[Dict]:
        if not lease_ids:
            return []

        cursor.execute(self.SELECT_LEASES_SQL, (lease_ids,))
        rows = cursor.fetchall() or []
        leases: List[Dict] = []
        for lease_id, task_id, asset_id, tenant_id, project_id, meta_spec in rows:
            leases.append(
                {
                    "lease_id": lease_id,
                    "task_id": task_id,
                    "asset_id": asset_id,
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "meta_spec": meta_spec,
                }
            )
        return leases

    def _execute_task(self, task_type: str, leases: List[Dict]) -> bool:
        del task_type
        acquired_assets: List[str] = []
        try:
            for lease in leases:
                specs = lease.get("meta_spec") or {}
                payload = self.adapter.acquire(specs)
                acquired_assets.append(payload.get("asset_id", lease.get("asset_id")))

            for asset_id in acquired_assets:
                health = self.adapter.check_health(asset_id)
                if health.get("status") == "unhealthy":
                    return False

            return True
        except AdapterError:
            LOGGER.exception("Adapter failure while executing task")
            return False
        finally:
            for asset_id in acquired_assets:
                try:
                    self.adapter.release(asset_id)
                except AdapterError:
                    LOGGER.exception("Adapter failed to release asset %s", asset_id)

    def _settle_success(self, cursor, task_id: str, leases: List[Dict]) -> None:
        asset_ids = [lease["asset_id"] for lease in leases]
        lease_ids = [lease["lease_id"] for lease in leases]
        cursor.execute(self.UPDATE_TASK_SUCCESS_SQL, (task_id,))
        if lease_ids:
            cursor.execute(self.UPDATE_LEASE_SUCCESS_SQL, (lease_ids,))
        if asset_ids:
            cursor.execute(self.UPDATE_ASSET_COOLING_SQL, (asset_ids,))
            for lease in leases:
                cursor.execute(
                    self.INSERT_EVENT_SQL,
                    (lease["asset_id"], "TASK_SUCCESS", "INFO", None),
                )
                cursor.execute(
                    self.INSERT_LEDGER_SQL,
                    (
                        lease["asset_id"],
                        lease.get("tenant_id"),
                        lease.get("project_id"),
                        "OUT",
                        "TASK_BURN",
                        0.01,
                    ),
                )

    def _settle_failure(
        self,
        cursor,
        task_id: str,
        leases: List[Dict],
        result_code: str,
        lease_ids: List[str],
    ) -> None:
        asset_ids = [lease["asset_id"] for lease in leases]
        cursor.execute(self.UPDATE_TASK_FAILURE_SQL, (result_code, task_id))
        if lease_ids:
            cursor.execute(self.UPDATE_LEASE_FAILURE_SQL, (lease_ids,))
        if asset_ids:
            cursor.execute(self.UPDATE_ASSET_FAILURE_SQL, (asset_ids,))
            for lease in leases:
                cursor.execute(
                    self.INSERT_EVENT_SQL,
                    (lease["asset_id"], "TASK_FAIL", "ERROR", result_code),
                )
                cursor.execute(
                    self.INSERT_LEDGER_SQL,
                    (
                        lease["asset_id"],
                        lease.get("tenant_id"),
                        lease.get("project_id"),
                        "OUT",
                        "TASK_BURN",
                        0.01,
                    ),
                )

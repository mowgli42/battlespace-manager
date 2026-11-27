"""SQLite persistence for mission-management authoritative state."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.mission.models import (
    Alert,
    Assignment,
    AuditEvent,
    Mission,
    Operator,
    PlatformOrg,
    Task,
    Team,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class MissionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # Keep a dedicated connection for :memory: so schema survives
        self._mem_conn: sqlite3.Connection | None = None
        if str(self.path) == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS teams (
                  team_id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operators (
                  operator_id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS missions (
                  mission_id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS platforms_org (
                  platform_id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                  task_id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assignments (
                  assignment_id TEXT PRIMARY KEY,
                  task_id TEXT NOT NULL,
                  request_id TEXT,
                  payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_assignments_task ON assignments(task_id);
                CREATE INDEX IF NOT EXISTS idx_assignments_request ON assignments(request_id);
                CREATE TABLE IF NOT EXISTS audit_events (
                  event_id TEXT PRIMARY KEY,
                  entity_type TEXT NOT NULL,
                  entity_id TEXT NOT NULL,
                  payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_type, entity_id);
                CREATE TABLE IF NOT EXISTS alerts (
                  alert_id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS utilization_samples (
                  sample_id TEXT PRIMARY KEY,
                  sampled_at TEXT NOT NULL,
                  platform_id TEXT NOT NULL,
                  payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_util_platform_time
                  ON utilization_samples(platform_id, sampled_at);
                """
            )
            if self._mem_conn is None:
                conn.commit()
                conn.close()

    def get_meta(self, key: str) -> str | None:
        with self._lock:
            conn = self._connect()
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            if self._mem_conn is None:
                conn.close()
            return None if row is None else str(row["value"])

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            if self._mem_conn is None:
                conn.commit()
                conn.close()

    def _put(self, table: str, pk: str, pk_val: str, payload: dict[str, Any]) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(
                f"INSERT INTO {table}({pk}, payload) VALUES(?, ?) "
                f"ON CONFLICT({pk}) DO UPDATE SET payload = excluded.payload",
                (pk_val, json.dumps(payload)),
            )
            if self._mem_conn is None:
                conn.commit()
                conn.close()

    def _get(self, table: str, pk: str, pk_val: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            row = conn.execute(f"SELECT payload FROM {table} WHERE {pk} = ?", (pk_val,)).fetchone()
            if self._mem_conn is None:
                conn.close()
            return None if row is None else json.loads(row["payload"])

    def _list(self, table: str) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            rows = conn.execute(f"SELECT payload FROM {table}").fetchall()
            if self._mem_conn is None:
                conn.close()
            return [json.loads(r["payload"]) for r in rows]

    def _delete(self, table: str, pk: str, pk_val: str) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(f"DELETE FROM {table} WHERE {pk} = ?", (pk_val,))
            if self._mem_conn is None:
                conn.commit()
                conn.close()

    # --- typed helpers ---

    def upsert_team(self, team: Team) -> None:
        self._put("teams", "team_id", team.team_id, team.to_dict())

    def get_team(self, team_id: str) -> Team | None:
        raw = self._get("teams", "team_id", team_id)
        return Team(**raw) if raw else None

    def list_teams(self) -> list[Team]:
        return [Team(**r) for r in self._list("teams")]

    def upsert_operator(self, op: Operator) -> None:
        self._put("operators", "operator_id", op.operator_id, op.to_dict())

    def get_operator(self, operator_id: str) -> Operator | None:
        raw = self._get("operators", "operator_id", operator_id)
        return Operator(**raw) if raw else None

    def list_operators(self) -> list[Operator]:
        return [Operator(**r) for r in self._list("operators")]

    def upsert_mission(self, mission: Mission) -> None:
        self._put("missions", "mission_id", mission.mission_id, mission.to_dict())

    def get_mission(self, mission_id: str) -> Mission | None:
        raw = self._get("missions", "mission_id", mission_id)
        return Mission(**raw) if raw else None

    def list_missions(self) -> list[Mission]:
        return [Mission(**r) for r in self._list("missions")]

    def upsert_platform(self, platform: PlatformOrg) -> None:
        self._put("platforms_org", "platform_id", platform.platform_id, platform.to_dict())

    def get_platform(self, platform_id: str) -> PlatformOrg | None:
        raw = self._get("platforms_org", "platform_id", platform_id)
        return PlatformOrg(**raw) if raw else None

    def list_platforms(self) -> list[PlatformOrg]:
        return [PlatformOrg(**r) for r in self._list("platforms_org")]

    def upsert_task(self, task: Task) -> None:
        self._put("tasks", "task_id", task.task_id, task.to_dict())

    def get_task(self, task_id: str) -> Task | None:
        raw = self._get("tasks", "task_id", task_id)
        return Task(**raw) if raw else None

    def list_tasks(self) -> list[Task]:
        return [Task(**r) for r in self._list("tasks")]

    def upsert_assignment(self, assignment: Assignment) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO assignments(assignment_id, task_id, request_id, payload) VALUES(?, ?, ?, ?) "
                "ON CONFLICT(assignment_id) DO UPDATE SET task_id = excluded.task_id, "
                "request_id = excluded.request_id, payload = excluded.payload",
                (
                    assignment.assignment_id,
                    assignment.task_id,
                    assignment.request_id or None,
                    json.dumps(assignment.to_dict()),
                ),
            )
            if self._mem_conn is None:
                conn.commit()
                conn.close()

    def get_assignment(self, assignment_id: str) -> Assignment | None:
        raw = self._get("assignments", "assignment_id", assignment_id)
        return Assignment(**raw) if raw else None

    def find_assignment_by_request_id(self, request_id: str) -> Assignment | None:
        if not request_id:
            return None
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT payload FROM assignments WHERE request_id = ? ORDER BY assignment_id LIMIT 1",
                (request_id,),
            ).fetchone()
            if self._mem_conn is None:
                conn.close()
            return Assignment(**json.loads(row["payload"])) if row else None

    def list_assignments(self, task_id: str | None = None) -> list[Assignment]:
        with self._lock:
            conn = self._connect()
            if task_id:
                rows = conn.execute(
                    "SELECT payload FROM assignments WHERE task_id = ?", (task_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT payload FROM assignments").fetchall()
            if self._mem_conn is None:
                conn.close()
            return [Assignment(**json.loads(r["payload"])) for r in rows]

    def append_audit(self, event: AuditEvent) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO audit_events(event_id, entity_type, entity_id, payload) VALUES(?, ?, ?, ?)",
                (event.event_id, event.entity_type, event.entity_id, json.dumps(event.to_dict())),
            )
            if self._mem_conn is None:
                conn.commit()
                conn.close()

    def list_audit(self, entity_type: str | None = None, entity_id: str | None = None) -> list[AuditEvent]:
        with self._lock:
            conn = self._connect()
            if entity_type and entity_id:
                rows = conn.execute(
                    "SELECT payload FROM audit_events WHERE entity_type = ? AND entity_id = ?",
                    (entity_type, entity_id),
                ).fetchall()
            else:
                rows = conn.execute("SELECT payload FROM audit_events").fetchall()
            if self._mem_conn is None:
                conn.close()
            return [AuditEvent(**json.loads(r["payload"])) for r in rows]

    def upsert_alert(self, alert: Alert) -> None:
        self._put("alerts", "alert_id", alert.alert_id, alert.to_dict())

    def get_alert(self, alert_id: str) -> Alert | None:
        raw = self._get("alerts", "alert_id", alert_id)
        return Alert(**raw) if raw else None

    def list_alerts(self) -> list[Alert]:
        return [Alert(**r) for r in self._list("alerts")]

    def append_utilization_sample(self, sample: dict[str, Any]) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO utilization_samples(sample_id, sampled_at, platform_id, payload) VALUES(?, ?, ?, ?)",
                (
                    sample["sample_id"],
                    sample["sampled_at"],
                    sample["platform_id"],
                    json.dumps(sample),
                ),
            )
            if self._mem_conn is None:
                conn.commit()
                conn.close()

    def list_utilization_samples(
        self,
        *,
        platform_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            sql = "SELECT payload FROM utilization_samples WHERE 1=1"
            params: list[Any] = []
            if platform_id:
                sql += " AND platform_id = ?"
                params.append(platform_id)
            if start:
                sql += " AND sampled_at >= ?"
                params.append(start)
            if end:
                sql += " AND sampled_at <= ?"
                params.append(end)
            sql += " ORDER BY sampled_at ASC"
            rows = conn.execute(sql, params).fetchall()
            if self._mem_conn is None:
                conn.close()
            return [json.loads(r["payload"]) for r in rows]

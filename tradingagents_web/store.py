from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import REPORT_SECTIONS, RunSpec

MAX_INLINE_EVENT_TEXT_LENGTH = 1600
MAX_INLINE_EVENTS = 300


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_web_home() -> Path:
    return Path(
        os.environ.get("TRADINGAGENTS_WEB_HOME", "~/.tradingagents/web")
    ).expanduser()


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    compacted = dict(event)
    for key in ("content", "message", "traceback"):
        value = compacted.get(key)
        if isinstance(value, str) and len(value) > MAX_INLINE_EVENT_TEXT_LENGTH:
            compacted[key] = value[:MAX_INLINE_EVENT_TEXT_LENGTH].rstrip() + "\n..."
            compacted[f"{key}_truncated"] = True
            compacted[f"{key}_original_size"] = len(value)
    return compacted


class RunStore:
    """Small local store for web runs.

    SQLite owns run metadata. Per-run JSONL and Markdown files keep live
    events and reports simple to inspect outside the app.
    """

    def __init__(self, home: Path | None = None):
        self.home = home or default_web_home()
        self.db_path = self.home / "tradingagents-web.db"
        self.runs_dir = self.home / "runs"
        self.home.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    analysis_date TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    analysts_json TEXT NOT NULL,
                    llm_provider TEXT NOT NULL,
                    quick_model TEXT NOT NULL,
                    deep_model TEXT NOT NULL,
                    research_depth INTEGER NOT NULL,
                    output_language TEXT NOT NULL,
                    run_dir TEXT NOT NULL,
                    pid INTEGER,
                    error TEXT,
                    decision TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
                """
            )

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def events_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "events.jsonl"

    def spec_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "spec.json"

    def reports_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "reports"

    def create_run(self, spec: RunSpec) -> dict[str, Any]:
        run_id = uuid.uuid4().hex
        run_dir = self.run_dir(run_id)
        reports_dir = self.reports_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        self.spec_path(run_id).write_text(
            json.dumps(spec.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, status, ticker, analysis_date, asset_type, analysts_json,
                    llm_provider, quick_model, deep_model, research_depth,
                    output_language, run_dir, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    "pending",
                    spec.ticker,
                    spec.analysis_date,
                    spec.asset_type,
                    json.dumps(spec.analysts),
                    spec.llm_provider,
                    spec.quick_think_llm,
                    spec.deep_think_llm,
                    spec.research_depth,
                    spec.output_language,
                    str(run_dir),
                    now,
                    now,
                ),
            )
        self.append_event(run_id, "run_created", spec=spec.to_dict())
        return self.get_run(run_id)

    def load_spec(self, run_id: str) -> RunSpec:
        return RunSpec.from_dict(
            json.loads(self.spec_path(run_id).read_text(encoding="utf-8"))
        )

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["analysts"] = json.loads(data.pop("analysts_json"))
        data["reports"] = self.list_reports(data["id"], include_content=True)
        events, next_index = self.read_events(data["id"])
        data["events"] = [compact_event(event) for event in events[-MAX_INLINE_EVENTS:]]
        data["event_next"] = next_index
        return data

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return self._row_to_dict(row)

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_run(self, run_id: str, **fields: Any) -> None:
        allowed = {
            "status",
            "pid",
            "error",
            "decision",
            "started_at",
            "completed_at",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        updates["updated_at"] = utc_now()
        if not updates:
            return
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [run_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE runs SET {assignments} WHERE id = ?",
                values,
            )

    def append_event(self, run_id: str, event_type: str, **payload: Any) -> None:
        path = self.events_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "run_id": run_id,
            "type": event_type,
            "timestamp": utc_now(),
            **payload,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    def read_events(self, run_id: str, after: int = 0) -> tuple[list[dict[str, Any]], int]:
        path = self.events_path(run_id)
        if not path.exists():
            return [], after
        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index < after:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event["_index"] = index
                events.append(event)
        return events, after + len(events)

    def write_report(self, run_id: str, section: str, content: str) -> None:
        if section not in REPORT_SECTIONS:
            return
        path = self.reports_dir(run_id) / f"{section}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content or "", encoding="utf-8")

    def read_report(self, run_id: str, section: str) -> str | None:
        if section not in REPORT_SECTIONS:
            return None
        path = self.reports_dir(run_id) / f"{section}.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def list_reports(
        self,
        run_id: str,
        *,
        include_content: bool = False,
    ) -> dict[str, dict[str, Any]]:
        reports: dict[str, dict[str, Any]] = {}
        for section in REPORT_SECTIONS:
            path = self.reports_dir(run_id) / f"{section}.md"
            if path.exists():
                stat = path.stat()
                reports[section] = {
                    "section": section,
                    "size": stat.st_size,
                    "updated_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
                if include_content:
                    reports[section]["content"] = path.read_text(encoding="utf-8")
        return reports

from __future__ import annotations

import asyncio
import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tradingagents.default_config import DEFAULT_CONFIG

from .models import ANALYST_OPTIONS, PROVIDER_OPTIONS, REPORT_SECTIONS, TERMINAL_STATUSES, RunSpec
from .store import RunStore, compact_event, utc_now


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
class RunCreate(BaseModel):
    ticker: str = Field(..., min_length=1)
    analysis_date: str = Field(..., min_length=10, max_length=10)
    analysts: list[str] = Field(default_factory=lambda: ["market"])
    research_depth: int = Field(default=1, ge=1, le=5)
    llm_provider: str = "openai"
    quick_think_llm: str = DEFAULT_CONFIG["quick_think_llm"]
    deep_think_llm: str = DEFAULT_CONFIG["deep_think_llm"]
    output_language: str = "Chinese"
    asset_type: str = "stock"
    backend_url: str | None = None
    checkpoint_enabled: bool = False
    google_thinking_level: str | None = None
    openai_reasoning_effort: str | None = None
    anthropic_effort: str | None = None

    def to_spec(self) -> RunSpec:
        return RunSpec.from_dict(self.model_dump())


def create_app() -> FastAPI:
    app = FastAPI(title="TradingAgents Web", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=(
            r"https?://("
            r"localhost|127\.0\.0\.1|0\.0\.0\.0|"
            r"10\.\d+\.\d+\.\d+|"
            r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|"
            r"192\.168\.\d+\.\d+"
            r")(:\d+)?"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.store = RunStore()

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True}

    @app.get("/api/options")
    def options() -> dict[str, Any]:
        return {
            "analysts": ANALYST_OPTIONS,
            "providers": PROVIDER_OPTIONS,
            "report_sections": REPORT_SECTIONS,
            "defaults": {
                "research_depth": 1,
                "llm_provider": DEFAULT_CONFIG["llm_provider"],
                "quick_think_llm": DEFAULT_CONFIG["quick_think_llm"],
                "deep_think_llm": DEFAULT_CONFIG["deep_think_llm"],
                "output_language": "Chinese",
                "analysis_date": None,
            },
        }

    @app.post("/api/runs")
    def create_run(payload: RunCreate) -> dict[str, Any]:
        store: RunStore = app.state.store
        run = store.create_run(payload.to_spec())
        run_id = run["id"]
        log_path = store.run_dir(run_id) / "runner.log"
        log_handle = log_path.open("ab")
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        proc = subprocess.Popen(
            [sys.executable, "-m", "tradingagents_web.runner", run_id],
            cwd=str(REPO_ROOT),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
        )
        log_handle.close()
        store.update_run(run_id, pid=proc.pid)
        store.append_event(run_id, "process_started", pid=proc.pid)
        return store.get_run(run_id)

    @app.get("/api/runs")
    def list_runs(limit: int = Query(100, ge=1, le=500)) -> list[dict[str, Any]]:
        return app.state.store.list_runs(limit=limit)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = app.state.store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.get("/api/runs/{run_id}/events")
    def get_events(
        run_id: str,
        after: int = Query(0, ge=0),
        compact: bool = Query(True),
    ) -> dict[str, Any]:
        if app.state.store.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")
        events, next_index = app.state.store.read_events(run_id, after=after)
        if compact:
            events = [compact_event(event) for event in events]
        return {"events": events, "next": next_index}

    @app.get("/api/events")
    def get_events_flat(
        run_id: str = Query(...),
        after: int = Query(0, ge=0),
        compact: bool = Query(True),
    ) -> dict[str, Any]:
        return get_events(run_id=run_id, after=after, compact=compact)

    @app.get("/api/runs/{run_id}/stream")
    async def stream_events(run_id: str, after: int = Query(0, ge=0)):
        store: RunStore = app.state.store
        if store.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")

        async def generate():
            index = after
            idle_after_terminal = False
            while True:
                events, index = store.read_events(run_id, after=index)
                for event in events:
                    event = compact_event(event)
                    payload = json.dumps(event, ensure_ascii=False)
                    yield (
                        f"id: {event.get('_index', index)}\n"
                        f"event: {event['type']}\n"
                        f"data: {payload}\n\n"
                    )
                run = store.get_run(run_id)
                if run and run["status"] in TERMINAL_STATUSES:
                    if idle_after_terminal:
                        break
                    idle_after_terminal = True
                await asyncio.sleep(1)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/stream")
    async def stream_events_flat(run_id: str = Query(...), after: int = Query(0, ge=0)):
        return await stream_events(run_id=run_id, after=after)

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> dict[str, Any]:
        store: RunStore = app.state.store
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] in TERMINAL_STATUSES:
            return run
        pid = run.get("pid")
        if pid:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        store.update_run(run_id, status="canceled", completed_at=utc_now())
        store.append_event(run_id, "run_canceled", reason="user_requested")
        return store.get_run(run_id)

    @app.get("/api/runs/{run_id}/reports")
    def list_reports(run_id: str) -> dict[str, Any]:
        if app.state.store.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return app.state.store.list_reports(run_id)

    @app.get("/api/runs/{run_id}/reports/{section}", response_class=PlainTextResponse)
    def get_report(run_id: str, section: str) -> str:
        report = app.state.store.read_report(run_id, section)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    @app.get("/api/report", response_class=PlainTextResponse)
    def get_report_flat(run_id: str = Query(...), section: str = Query(...)) -> str:
        return get_report(run_id=run_id, section=section)

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}")
        def frontend(path: str):
            candidate = FRONTEND_DIST / path
            if path and candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:
        @app.get("/")
        def root() -> dict[str, str]:
            return {
                "message": "TradingAgents Web API is running. Start the Vite frontend in ./frontend.",
            }

    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TradingAgents Web server.")
    parser.add_argument(
        "--host",
        default=os.environ.get("TRADINGAGENTS_WEB_HOST", "127.0.0.1"),
        help="Bind host. Use 0.0.0.0 to allow LAN access.",
    )
    parser.add_argument(
        "--port",
        default=int(os.environ.get("TRADINGAGENTS_WEB_PORT", "8000")),
        type=int,
        help="Bind port.",
    )
    args = parser.parse_args()
    uvicorn.run("tradingagents_web.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()

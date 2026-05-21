from __future__ import annotations

import argparse
import os
import signal
import sys
import traceback
from typing import Any

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

from .adapters import message_event, report_updates, tool_call_events
from .store import RunStore, utc_now


store: RunStore | None = None
current_run_id: str | None = None


def emit(event_type: str, **payload: Any) -> None:
    if store is not None and current_run_id is not None:
        store.append_event(current_run_id, event_type, **payload)


def handle_sigterm(signum, frame) -> None:
    if store is not None and current_run_id is not None:
        store.update_run(
            current_run_id,
            status="canceled",
            completed_at=utc_now(),
        )
        emit("run_canceled", reason="terminated")
    raise SystemExit(130)


def build_config(spec) -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = spec.research_depth
    config["max_risk_discuss_rounds"] = spec.research_depth
    config["quick_think_llm"] = spec.quick_think_llm
    config["deep_think_llm"] = spec.deep_think_llm
    config["backend_url"] = spec.backend_url
    config["llm_provider"] = spec.llm_provider.lower()
    config["output_language"] = spec.output_language
    config["checkpoint_enabled"] = spec.checkpoint_enabled
    config["google_thinking_level"] = spec.google_thinking_level
    config["openai_reasoning_effort"] = spec.openai_reasoning_effort
    config["anthropic_effort"] = spec.anthropic_effort
    return config


def run(run_id: str) -> int:
    global store, current_run_id
    store = RunStore()
    current_run_id = run_id
    spec = store.load_spec(run_id)
    store.update_run(run_id, status="running", started_at=utc_now(), pid=os.getpid())
    emit("run_started", spec=spec.to_dict(), pid=os.getpid())

    final_state: dict[str, Any] = {}
    last_reports: dict[str, str] = {}

    try:
        graph = TradingAgentsGraph(
            selected_analysts=spec.analysts,
            config=build_config(spec),
            debug=True,
        )
        emit("graph_ready", analysts=spec.analysts)
        init_state = graph.propagator.create_initial_state(
            spec.ticker,
            spec.analysis_date,
            asset_type=spec.asset_type,
        )
        args = graph.propagator.get_graph_args()

        for chunk in graph.graph.stream(init_state, **args):
            final_state.update(chunk)

            for message in chunk.get("messages", []) or []:
                event = message_event(message)
                if event:
                    event_type, payload = event
                    emit(event_type, **payload)
                for tool_call in tool_call_events(message):
                    emit("tool_call", **tool_call)

            for section, content in report_updates(chunk).items():
                if last_reports.get(section) == content:
                    continue
                last_reports[section] = content
                store.write_report(run_id, section, content)
                emit("report_updated", section=section, size=len(content))

        decision = ""
        final_decision = final_state.get("final_trade_decision")
        if final_decision:
            decision = graph.process_signal(str(final_decision))
            emit("decision_updated", decision=decision)

        store.update_run(
            run_id,
            status="completed",
            completed_at=utc_now(),
            decision=decision,
        )
        emit("run_completed", decision=decision)
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        error = "".join(traceback.format_exception(exc))
        store.update_run(
            run_id,
            status="failed",
            completed_at=utc_now(),
            error=error,
        )
        emit("error", message=str(exc), traceback=error)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, handle_sigterm)
    return run(args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage


REPORT_KEYS = (
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "trader_investment_plan",
    "final_trade_decision",
)


def message_event(message: Any) -> tuple[str, dict[str, Any]] | None:
    content = getattr(message, "content", "")
    if isinstance(content, list):
        content = "\n".join(str(item) for item in content)
    if not content:
        return None

    role = "message"
    if isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, SystemMessage):
        role = "system"
    elif isinstance(message, ToolMessage):
        role = "tool"
    elif isinstance(message, AIMessage):
        role = "agent"
    return "message", {"role": role, "content": str(content)}


def tool_call_events(message: Any) -> list[dict[str, Any]]:
    events = []
    for call in getattr(message, "tool_calls", []) or []:
        if isinstance(call, dict):
            name = call.get("name")
            args = call.get("args")
        else:
            name = getattr(call, "name", None)
            args = getattr(call, "args", None)
        events.append({"name": name or "tool", "args": args or {}})
    return events


def _state_get(state: Any, key: str, default: str = "") -> str:
    if isinstance(state, dict):
        return state.get(key, default) or default
    return getattr(state, key, default) or default


def investment_plan_from_state(state: Any) -> str:
    parts = []
    bull = _state_get(state, "bull_history").strip()
    bear = _state_get(state, "bear_history").strip()
    judge = _state_get(state, "judge_decision").strip()
    if bull:
        parts.append(f"### Bull Researcher Analysis\n{bull}")
    if bear:
        parts.append(f"### Bear Researcher Analysis\n{bear}")
    if judge:
        parts.append(f"### Research Manager Decision\n{judge}")
    return "\n\n".join(parts)


def final_decision_from_risk_state(state: Any) -> str:
    parts = []
    aggressive = _state_get(state, "aggressive_history").strip()
    conservative = _state_get(state, "conservative_history").strip()
    neutral = _state_get(state, "neutral_history").strip()
    judge = _state_get(state, "judge_decision").strip()
    if aggressive:
        parts.append(f"### Aggressive Analyst Analysis\n{aggressive}")
    if conservative:
        parts.append(f"### Conservative Analyst Analysis\n{conservative}")
    if neutral:
        parts.append(f"### Neutral Analyst Analysis\n{neutral}")
    if judge:
        parts.append(f"### Portfolio Manager Decision\n{judge}")
    return "\n\n".join(parts)


def report_updates(chunk: dict[str, Any]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for key in REPORT_KEYS:
        value = chunk.get(key)
        if value:
            updates[key] = str(value)
    if chunk.get("investment_debate_state"):
        value = investment_plan_from_state(chunk["investment_debate_state"])
        if value:
            updates["investment_plan"] = value
    if chunk.get("risk_debate_state"):
        value = final_decision_from_risk_state(chunk["risk_debate_state"])
        if value:
            updates["final_trade_decision"] = value
    return updates

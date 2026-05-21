from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


TERMINAL_STATUSES = {"completed", "failed", "canceled"}

ANALYST_OPTIONS = [
    {"value": "market", "label": "Market Analyst"},
    {"value": "social", "label": "Sentiment Analyst"},
    {"value": "news", "label": "News Analyst"},
    {"value": "fundamentals", "label": "Fundamentals Analyst"},
]

PROVIDER_OPTIONS = [
    {"value": "openai", "label": "OpenAI"},
    {"value": "anthropic", "label": "Anthropic"},
    {"value": "google", "label": "Google Gemini"},
    {"value": "deepseek", "label": "DeepSeek"},
    {"value": "qwen", "label": "Qwen"},
    {"value": "qwen-cn", "label": "Qwen China"},
    {"value": "glm", "label": "GLM"},
    {"value": "glm-cn", "label": "GLM China"},
    {"value": "minimax", "label": "MiniMax"},
    {"value": "minimax-cn", "label": "MiniMax China"},
    {"value": "openrouter", "label": "OpenRouter"},
    {"value": "ollama", "label": "Ollama"},
]

REPORT_SECTIONS = [
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
]


@dataclass
class RunSpec:
    ticker: str
    analysis_date: str
    analysts: list[str] = field(default_factory=lambda: ["market"])
    research_depth: int = 1
    llm_provider: str = "openai"
    quick_think_llm: str = "gpt-5.4-mini"
    deep_think_llm: str = "gpt-5.4"
    output_language: str = "Chinese"
    asset_type: str = "stock"
    backend_url: str | None = None
    checkpoint_enabled: bool = False
    google_thinking_level: str | None = None
    openai_reasoning_effort: str | None = None
    anthropic_effort: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunSpec":
        normalized = dict(data)
        normalized["ticker"] = str(normalized["ticker"]).strip().upper()
        normalized["analysis_date"] = str(normalized["analysis_date"]).strip()
        normalized["analysts"] = [
            str(value).strip().lower()
            for value in normalized.get("analysts") or ["market"]
            if str(value).strip()
        ]
        normalized["research_depth"] = int(normalized.get("research_depth") or 1)
        normalized["checkpoint_enabled"] = bool(
            normalized.get("checkpoint_enabled", False)
        )
        return cls(**normalized)

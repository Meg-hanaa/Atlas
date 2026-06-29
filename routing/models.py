"""Shared cascadeflow model configs and async helpers."""

from __future__ import annotations

import asyncio
import os
from functools import lru_cache

from cascadeflow import CascadeAgent, ModelConfig

from config import ensure_groq_key
from monitoring.tracing import set_span_attributes, trace_span

# Groq pricing approximations ($/token) for cost tracking
CHEAP_MODEL = "qwen/qwen3-32b"
STRONG_MODEL = "openai/gpt-oss-120b"
CHEAP_COST = 0.00000029  # ~$0.29/1M tokens
STRONG_COST = 0.0000015  # ~$1.50/1M tokens


def _groq_key() -> str:
    return ensure_groq_key()


@lru_cache
def chat_agent() -> CascadeAgent:
    """Chat/search: cheap first, escalate on quality failure."""
    return CascadeAgent(
        models=[
            ModelConfig(
                name=CHEAP_MODEL,
                provider="groq",
                cost=CHEAP_COST,
                api_key=_groq_key(),
            ),
            ModelConfig(
                name=STRONG_MODEL,
                provider="groq",
                cost=STRONG_COST,
                api_key=_groq_key(),
            ),
        ],
        quality={
            "threshold": 0.45,
            "require_minimum_tokens": 8,
        },
    )


@lru_cache
def flashcard_agent() -> CascadeAgent:
    """Flashcard generation: draft cheap, escalate if quality check fails."""
    return CascadeAgent(
        models=[
            ModelConfig(
                name=CHEAP_MODEL,
                provider="groq",
                cost=CHEAP_COST,
                api_key=_groq_key(),
            ),
            ModelConfig(
                name=STRONG_MODEL,
                provider="groq",
                cost=STRONG_COST,
                api_key=_groq_key(),
            ),
        ],
        quality={
            "threshold": 0.5,
            "require_minimum_tokens": 15,
        },
    )


@lru_cache
def grading_agent() -> CascadeAgent:
    """Quiz answer grading — always start cheap."""
    return CascadeAgent(
        models=[
            ModelConfig(
                name=CHEAP_MODEL,
                provider="groq",
                cost=CHEAP_COST,
                api_key=_groq_key(),
            ),
            ModelConfig(
                name=STRONG_MODEL,
                provider="groq",
                cost=STRONG_COST,
                api_key=_groq_key(),
            ),
        ],
        quality={"threshold": 0.4, "require_minimum_tokens": 3},
    )


def run_async(coro):
    """Run async cascadeflow calls from sync Streamlit code."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import nest_asyncio

    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


async def cascade_run(
    agent: CascadeAgent,
    prompt: str,
    max_tokens: int = 512,
    operation: str = "cascadeflow.run",
):
    os.environ.setdefault("GROQ_API_KEY", _groq_key())
    with trace_span(operation, {"prompt_length": len(prompt), "max_tokens": max_tokens}) as span:
        result = await agent.run(prompt, max_tokens=max_tokens)
        set_span_attributes(
            span,
            model_used=result.model_used,
            total_cost=result.total_cost,
            cascaded=result.cascaded,
            quality_check_passed=result.quality_check_passed,
            draft_accepted=result.draft_accepted,
        )
        return result


def format_ai_meta(model_used: str, total_cost: float, recall_strength: float | None = None) -> str:
    parts = [f"model: {model_used}", f"cost: ${total_cost:.6f}"]
    if recall_strength is not None:
        parts.append(f"recall_strength: {recall_strength:.2f}")
    return " · ".join(parts)

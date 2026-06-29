"""Chat service — grounded Q&A via recall + cascadeflow."""

from __future__ import annotations

from monitoring.events import set_span_attributes, trace_span
from memory.bank import search_memories
from routing.models import cascade_run, chat_agent


async def chat_with_notes(user_id: str, question: str, subject: str) -> dict:
    with trace_span("chat.answer", {"question_length": len(question), "subject": subject, "user_id": user_id}) as span:
        memories = search_memories(user_id, question, subject=subject)
        grounded = len(memories) > 0
        context = "\n".join(f"- {m}" for m in memories) or "(no memories found)"
        prompt = f"""\
You are Atlas, a personal ML study assistant. Answer using ONLY the recalled notes below.
If the notes don't contain enough info, say so briefly.

Recalled notes:
{context}

User question: {question}
"""
        result = await cascade_run(chat_agent(), prompt, max_tokens=600, operation="cascadeflow.chat")
        set_span_attributes(
            span,
            recall_hit_count=len(memories),
            grounded=grounded,
            model_used=result.model_used,
            total_cost=result.total_cost,
            cascaded=result.cascaded,
        )
    return {
        "answer": result.content,
        "model_used": result.model_used,
        "total_cost": result.total_cost,
        "memories": memories,
        "grounded": grounded,
    }

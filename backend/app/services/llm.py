"""
Groq LLM service with multi-turn conversation memory.
History is passed in from Neon PostgreSQL.
"""

import logging
from typing import Generator

from groq import Groq
from ..core.config import settings

_client: Groq | None = None
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are PolicyPal — a helpful AI assistant that answers questions about company policies, HR documents, and internal guidelines.

Rules:
- Answer ONLY from the policy context provided. Do not invent policies.
- Be concise and clear. Use bullet points for multi-step answers.
- If a question cannot be answered from the context, say: "I don't see that covered in the uploaded policies. Please consult HR directly."
- Reference the document source when relevant (e.g. "According to the Remote Work Policy...").
- Never provide legal advice — always remind users to consult an HR professional for binding interpretations."""


def _get_client() -> Groq:
    global _client
    if _client is None:
        logger.info("Initializing Groq client for PolicyPal")
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def stream_answer(
    question: str,
    context_chunks: list[dict],
    history: list[dict],
) -> Generator[str, None, None]:
    """
    Yield streaming tokens. `history` is a list of {role, content} dicts (chronological).
    """
    logger.info(
        "Streaming PolicyPal answer with %d context chunks and %d history messages",
        len(context_chunks),
        len(history),
    )
    context_text = "\n\n---\n\n".join(
        f"[{c['source_file']} — page {c['page']}]\n{c['content']}" if c.get("page") else
        f"[{c['source_file']}]\n{c['content']}"
        for c in context_chunks
    )

    # Build messages: system → history → context + new question
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-8:]:   # keep last 8 turns (4 exchanges) to stay within context
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({
        "role": "user",
        "content": f"Policy context:\n\n{context_text}\n\n---\n\nQuestion: {question}",
    })

    stream = _get_client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        max_tokens=800,
        temperature=0.1,
        stream=True,
    )

    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token

"""vLLM OpenAI-compatible client + thinking-mode helpers for Gemma 4.

Thinking mode requires the server to be launched with
  --reasoning-parser gemma4 --chat-template <path>/tool_chat_template_gemma4.jinja
and the request to opt in via chat_template_kwargs.enable_thinking=True.
"""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8000/v1")
MODEL = "google/gemma-4-31B-it"

vllm_client = OpenAI(base_url=VLLM_URL, api_key="EMPTY")

# Raw thought delimiters are asymmetric: <|channel>thought ... <channel|>
_THOUGHT_RE = re.compile(r"<\|channel>\s*thought\s*\n?(.*?)<channel\|>", re.DOTALL)


def _split_thought(content: str) -> tuple[str, str]:
    if "<|channel>" not in content:
        return content, ""
    m = _THOUGHT_RE.search(content)
    if not m:
        return content, ""
    return _THOUGHT_RE.sub("", content).strip(), m.group(1).strip()


def classify_messages(messages, max_tokens: int = 64) -> str:
    """One non-thinking chat-completion call."""
    resp = vllm_client.chat.completions.create(
        model=MODEL, messages=messages,
        temperature=0.0, max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def classify_messages_thinking(messages, max_tokens: int = 4096) -> tuple[str, str]:
    """Return (content, reasoning). Requires server with --reasoning-parser gemma4."""
    resp = vllm_client.chat.completions.create(
        model=MODEL, messages=messages,
        temperature=0.0, max_tokens=max_tokens,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}},
    )
    msg = resp.choices[0].message
    content = msg.content or ""
    reasoning = (
        getattr(msg, "reasoning", None)
        or getattr(msg, "reasoning_content", None)
        or ""
    )
    if not reasoning:
        content, reasoning = _split_thought(content)
    return content, reasoning


def classify_batch(messages_list, max_tokens: int = 64, max_workers: int = 16) -> list[str]:
    """Concurrent non-thinking batch. Preserves input order."""
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(lambda m: classify_messages(m, max_tokens), messages_list))


def classify_batch_thinking(messages_list, max_tokens: int = 4096, max_workers: int = 16) -> list[tuple[str, str]]:
    """Concurrent thinking-mode batch. Preserves input order."""
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(lambda m: classify_messages_thinking(m, max_tokens), messages_list))

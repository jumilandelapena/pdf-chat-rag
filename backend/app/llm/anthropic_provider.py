"""Anthropic Messages API: streamed answers with native citations, Haiku rewrite and judge."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from app.config import Settings
from app.errors import ProviderError
from app.llm.prompts import JUDGE_PROMPT, JUDGE_SCHEMA, REWRITE_SYSTEM, build_request
from app.llm.provider import (
    AnswerRequest,
    Final,
    FinalTextBlock,
    HistoryTurn,
    JudgeResult,
    RawCitation,
    TextDelta,
    Usage,
)
from app.llm.rewrite import build_rewrite_messages, clean_rewrite_output

log = logging.getLogger(__name__)
API_ERRORS = (anthropic.APIStatusError, anthropic.APIConnectionError)


def usage_from(raw: Any) -> Usage:
    details = getattr(raw, "output_tokens_details", None)
    return Usage(
        input_tokens=raw.input_tokens or 0,
        output_tokens=raw.output_tokens or 0,
        cache_read_input_tokens=raw.cache_read_input_tokens or 0,
        cache_creation_input_tokens=raw.cache_creation_input_tokens or 0,
        thinking_tokens=(details.thinking_tokens if details else 0) or 0,
    )


def add_usage(a: Usage, b: Usage) -> Usage:
    return Usage(
        a.input_tokens + b.input_tokens,
        a.output_tokens + b.output_tokens,
        a.cache_read_input_tokens + b.cache_read_input_tokens,
        a.cache_creation_input_tokens + b.cache_creation_input_tokens,
        a.thinking_tokens + b.thinking_tokens,
    )


def thinking_can_be_disabled(model: str) -> bool:
    """Haiku 5.5 accepts ``thinking: disabled``; Opus 5.5 rejects it."""
    return "haiku" in model


def _text_of(message: Any) -> str:
    return "".join(block.text for block in message.content if block.type == "text")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key, timeout=120.0, max_retries=2
        )

    async def rewrite(self, question: str, history: list[HistoryTurn]) -> str:
        if not history:
            return question
        params: dict[str, Any] = {
            "model": self.settings.rewrite_model,
            "max_tokens": self.settings.rewrite_max_tokens,
            "system": REWRITE_SYSTEM,
            "messages": build_rewrite_messages(question, history, self.settings.history_turns),
            "output_config": {"effort": "low"},
        }
        if thinking_can_be_disabled(self.settings.rewrite_model):
            params["thinking"] = {"type": "disabled"}
        try:
            message = await self.client.messages.create(**params)
        except API_ERRORS as exc:
            log.warning("query rewrite failed, using the question as-is: %s", exc)
            return question
        if message.stop_reason != "end_turn":
            return question
        return clean_rewrite_output(_text_of(message), question)

    async def stream_answer(self, request: AnswerRequest) -> AsyncIterator[TextDelta | Final]:
        params, _ = build_request(self.settings, request)
        try:
            async with self.client.messages.stream(**params) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield TextDelta(event.delta.text)
                final = await stream.get_final_message()
        except API_ERRORS as exc:
            raise ProviderError(
                "provider_error", f"{type(exc).__name__}: {str(exc)[:300]}"
            ) from exc
        blocks = [
            FinalTextBlock(
                block.text,
                [
                    RawCitation(
                        c.document_index, c.cited_text, c.start_char_index, c.end_char_index
                    )
                    for c in (block.citations or [])
                    if c.type == "char_location"
                ],
            )
            for block in final.content
            if block.type == "text"
        ]
        yield Final(
            blocks=blocks,
            stop_reason=final.stop_reason,
            usage=usage_from(final.usage),
            model=final.model,
            stop_details_category=final.stop_details.category if final.stop_details else None,
            request_id=getattr(final, "_request_id", None),
        )

    async def judge(self, question: str, reference: str, excerpts: str, answer: str) -> JudgeResult:
        prompt = JUDGE_PROMPT.format(
            question=question, reference=reference, excerpts=excerpts, answer=answer
        )
        params: dict[str, Any] = {
            "model": self.settings.judge_model,
            "max_tokens": self.settings.judge_max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {
                "effort": "low",
                "format": {"type": "json_schema", "schema": JUDGE_SCHEMA},
            },
        }
        if thinking_can_be_disabled(self.settings.judge_model):
            params["thinking"] = {"type": "disabled"}
        total = Usage()
        for _attempt in range(2):
            try:
                message = await self.client.messages.create(**params)
            except API_ERRORS as exc:
                raise ProviderError(
                    "provider_error", f"{type(exc).__name__}: {str(exc)[:300]}"
                ) from exc
            total = add_usage(total, usage_from(message.usage))
            if message.stop_reason != "end_turn":
                continue
            try:
                data = json.loads(_text_of(message))
                score = int(data["score"])
            except (ValueError, KeyError, TypeError):
                continue
            return JudgeResult(
                score=min(5, max(1, score)),
                explanation=str(data.get("explanation", "")),
                usage=total,
                model=message.model,
            )
        return JudgeResult(None, "judge returned no usable JSON", total, self.settings.judge_model)

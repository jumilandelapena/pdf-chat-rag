from collections.abc import AsyncIterator

import pytest

from app.errors import ProviderError
from app.llm.provider import AnswerRequest, Final, FinalTextBlock, HistoryTurn, TextDelta, Usage
from tests.conftest import read_sse, upload


class StubProvider:
    name = "stub"

    def __init__(self, stop_reason: str | None, raise_error: bool = False) -> None:
        self.stop_reason = stop_reason
        self.raise_error = raise_error

    async def rewrite(self, question: str, history: list[HistoryTurn]) -> str:
        return question

    async def stream_answer(self, request: AnswerRequest) -> AsyncIterator[TextDelta | Final]:
        yield TextDelta("partial ")
        if self.raise_error:
            raise ProviderError("provider_error", "APIConnectionError: boom")
        yield Final(
            blocks=[FinalTextBlock("partial answer")],
            stop_reason=self.stop_reason,
            usage=Usage(10, 2),
            model="stub-model",
            stop_details_category="general_harms" if self.stop_reason == "refusal" else None,
        )

    async def judge(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise NotImplementedError


@pytest.mark.parametrize(
    ("stop_reason", "raise_error", "code"),
    [
        ("max_tokens", False, "max_tokens"),
        ("refusal", False, "refusal"),
        ("model_context_window_exceeded", False, "context_window"),
        (None, True, "provider_error"),
    ],
)
def test_bad_endings_emit_error_and_persist_nothing(
    client, app, sample_pdf, stop_reason, raise_error, code
) -> None:
    upload(client, sample_pdf)
    app.state.services.provider = StubProvider(stop_reason, raise_error)
    chat = client.post("/chats", json={}).json()
    response = client.post(f"/chats/{chat['id']}/messages", json={"content": "teapot?"})
    events = read_sse(response.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == code and events[-1][1]["message"]
    assert [name for name, _ in events if name == "token"] == ["token"]
    assert "citations" not in [name for name, _ in events]
    refreshed = client.get(f"/chats/{chat['id']}").json()
    assert refreshed["message_count"] == 0 and refreshed["messages"] == []

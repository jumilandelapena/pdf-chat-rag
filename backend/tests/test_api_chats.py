from pathlib import Path

from app.db import repo
from app.llm.provider import AnswerRequest
from tests.conftest import read_sse, upload


class RecordingProvider:
    name = "mock"

    def __init__(self, inner) -> None:  # noqa: ANN001
        self.inner = inner
        self.requests: list[AnswerRequest] = []

    async def rewrite(self, question, history):  # noqa: ANN001, ANN202
        return await self.inner.rewrite(question, history)

    def stream_answer(self, request):  # noqa: ANN001, ANN202
        self.requests.append(request)
        return self.inner.stream_answer(request)

    async def judge(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return await self.inner.judge(*args, **kwargs)


def stream(client, chat_id: str, content: str):  # noqa: ANN001, ANN201
    response = client.post(f"/chats/{chat_id}/messages", json={"content": content})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return read_sse(response.text)


def test_chat_crud_and_scope(client, sample_pdf: Path, tiny_pdf: Path) -> None:
    upload(client, sample_pdf)
    tiny = upload(client, tiny_pdf)
    chat = client.post("/chats", json={}).json()
    assert chat["document_ids"] == [] and chat["messages"] == [] and chat["message_count"] == 0
    assert client.post("/chats", json={"document_ids": ["nope"]}).status_code == 422
    scoped = client.post("/chats", json={"document_ids": [tiny["id"]], "title": "Tiny"}).json()
    assert scoped["document_ids"] == [tiny["id"]] and scoped["title"] == "Tiny"
    renamed = client.patch(f"/chats/{scoped['id']}", json={"title": "Renamed"}).json()
    assert renamed["document_ids"] == [tiny["id"]] and renamed["title"] == "Renamed"
    widened = client.patch(f"/chats/{scoped['id']}", json={"document_ids": []}).json()
    assert widened["document_ids"] == [] and widened["title"] == "Renamed"
    assert (
        client.patch(f"/chats/{scoped['id']}", json={"document_ids": ["nope"]}).status_code == 422
    )
    assert {c["id"] for c in client.get("/chats").json()} == {chat["id"], scoped["id"]}
    assert client.get("/chats/nope").status_code == 404
    assert client.delete(f"/chats/{scoped['id']}").status_code == 204
    assert client.get(f"/chats/{scoped['id']}").status_code == 404


def test_stream_persists_and_second_turn_resends_history(client, app, services, sample_pdf) -> None:
    rfc = upload(client, sample_pdf)
    provider = RecordingProvider(app.state.services.provider)
    app.state.services.provider = provider
    chat = client.post("/chats", json={}).json()
    question = "Which error does a teapot return when asked to brew coffee?"

    events = stream(client, chat["id"], question)
    names = [name for name, _ in events]
    assert names[0] == "status" and names[-1] == "done"
    assert set(names) == {"status", "token", "citations", "usage", "done"}
    assert names.index("citations") < names.index("usage") < names.index("done")
    assert [d["stage"] for n, d in events if n == "status"] == ["retrieving", "thinking"]
    text = "".join(d["text"] for n, d in events if n == "token")
    citations = next(d for n, d in events if n == "citations")
    assert 1 <= len(citations) <= 2 and citations[0]["n"] == 1
    with services.session_factory() as session:
        for cite in citations:
            assert cite["filename"] == "rfc2324-htcpcp.pdf" and cite["document_id"] == rfc["id"]
            page_text = repo.get_page_text(session, cite["document_id"], cite["page"])
            assert page_text[cite["page_char_start"] : cite["page_char_end"]] == cite["quote"]
            assert text[cite["text_start"] : cite["text_end"]] == cite["quote"].rstrip(".!?")
    usage = next(d for n, d in events if n == "usage")
    assert usage["model"] == "mock" and usage["cost_usd"] == 0
    done = next(d for n, d in events if n == "done")
    assert done["rewritten_query"] is None

    full = client.get(f"/chats/{chat['id']}").json()
    assert full["message_count"] == 2 and full["title"] == question[:60]
    user_msg, assistant_msg = full["messages"]
    assert user_msg["role"] == "user" and user_msg["content"] == question
    assert user_msg["id"] == done["user_message_id"] and user_msg["citations"] == []
    assert assistant_msg["id"] == done["message_id"] and assistant_msg["content"] == text
    assert assistant_msg["citations"] == citations and assistant_msg["usage"] == usage
    assert client.get("/chats").json()[0]["message_count"] == 2

    events2 = stream(client, chat["id"], "Which section defines it?")
    assert [d["stage"] for n, d in events2 if n == "status"] == [
        "rewriting",
        "retrieving",
        "thinking",
    ]
    assert (
        events2[-1][0] == "done"
        and events2[-1][1]["rewritten_query"] == "Which section defines it?"
    )
    second = provider.requests[-1]
    assert len(second.history) == 1 and second.history[0].user_text == question
    with services.session_factory() as session:
        stored_ids = repo.list_messages(session, chat["id"])[0].chunk_ids
    assert [c.chunk_id for c in second.history[0].chunks] == stored_ids
    assert len(stored_ids) == len(provider.requests[0].chunks)
    assert client.get(f"/chats/{chat['id']}").json()["message_count"] == 4


def test_errors_before_streaming_and_no_documents(client, tiny_pdf: Path) -> None:
    chat = client.post("/chats", json={}).json()
    events = stream(client, chat["id"], "anything?")
    assert events == [("error", events[0][1])] and events[0][1]["code"] == "no_documents"
    assert client.post(f"/chats/{chat['id']}/messages", json={"content": "   "}).status_code == 422
    assert client.post("/chats/nope/messages", json={"content": "hi"}).status_code == 404
    assert client.get(f"/chats/{chat['id']}").json()["message_count"] == 0
    tiny = upload(client, tiny_pdf)
    scoped = client.post("/chats", json={"document_ids": [tiny["id"]]}).json()
    events = stream(client, scoped["id"], "teapots and coffee brewing")
    assert events[-1][0] == "done"
    assert client.delete(f"/documents/{tiny['id']}").status_code == 204
    assert client.get(f"/chats/{scoped['id']}").json()["document_ids"] == []

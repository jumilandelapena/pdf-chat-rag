"""Run the golden set through the real pipeline and write docs/eval-results.md.

Usage:
  uv run evals/run.py                                   # real provider (needs ANTHROPIC_API_KEY)
  uv run evals/run.py --provider mock --embeddings fake --limit 3   # offline smoke run

Per question: recall@8 (expected page among the retrieved chunks), the streamed answer,
citation accuracy (cited pages vs expected pages), faithfulness 1-5 from the judge model,
latency, tokens and cost. Three rows also ask a scripted follow-up in the same chat, which
exercises the query rewrite and shows prompt-cache reads.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.chats import chunk_ref, load_history  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import repo  # noqa: E402
from app.ingest.pipeline import ingest_document  # noqa: E402
from app.llm.citations import citation_dict, map_citations  # noqa: E402
from app.llm.pricing import cost_usd, usage_dict  # noqa: E402
from app.llm.prompts import build_request, sort_chunks  # noqa: E402
from app.llm.provider import AnswerRequest, ChunkRef, Final, HistoryTurn, TextDelta  # noqa: E402
from app.retrieval.hybrid import retrieve  # noqa: E402
from app.services import AppServices, build_services  # noqa: E402
from evals.check_golden import DEFAULT_GOLDEN, DEFAULT_SAMPLES, load_golden  # noqa: E402
from evals.judge import judge_answer  # noqa: E402

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = EVALS_DIR.parents[1] / "docs" / "eval-results.md"


@dataclass
class Answer:
    text: str
    citations: list[dict[str, Any]]
    stop_reason: str | None
    usage: dict[str, Any]
    latency_s: float


@dataclass
class Row:
    id: str
    file: str
    question: str
    expected_pages: list[int]
    retrieved_pages: list[int] = field(default_factory=list)
    recall: bool = False
    answer: Answer | None = None
    cited_pages: list[int] = field(default_factory=list)
    citation_any: bool | None = None
    citation_all: bool | None = None
    faithfulness: int | None = None
    judge_explanation: str = ""
    judge_cost: float = 0.0
    follow_up: dict[str, Any] | None = None


async def stream_answer(services: AppServices, request: AnswerRequest) -> tuple[Answer, Final]:
    _, flat = build_request(services.settings, request)
    started = time.perf_counter()
    final: Final | None = None
    streamed = ""
    async for event in services.provider.stream_answer(request):
        if isinstance(event, TextDelta):
            streamed += event.text
        else:
            final = event
    latency = time.perf_counter() - started
    assert final is not None, "provider returned no final message"
    text, cites = map_citations(final.blocks, flat)
    assert text == streamed, "streamed tokens differ from the final text"
    answer = Answer(
        text=text,
        citations=[citation_dict(c) for c in cites],
        stop_reason=final.stop_reason,
        usage=usage_dict(final.usage, final.model),
        latency_s=round(latency, 2),
    )
    return answer, final


def ingest_samples(services: AppServices, files: list[str], samples_dir: Path) -> dict[str, str]:
    ids: dict[str, str] = {}
    for name in files:
        document_id = uuid.uuid4().hex
        dest = services.settings.uploads_dir / f"{document_id}.pdf"
        shutil.copyfile(samples_dir / name, dest)
        with services.session_factory() as session:
            repo.create_document(
                session,
                document_id=document_id,
                filename=name,
                stored_path=str(dest),
                size_bytes=dest.stat().st_size,
            )
        started = time.perf_counter()
        ingest_document(document_id, services)
        with services.session_factory() as session:
            doc = repo.get_document(session, document_id)
            assert doc is not None and doc.status == "ready", (
                f"{name}: {doc.error if doc else 'missing'}"
            )
            print(
                f"ingested {name}: {doc.page_count} pages, {doc.chunk_count} chunks in {time.perf_counter() - started:.1f}s"
            )
        ids[name] = document_id
    return ids


def score_citations(row: Row, answer: Answer, expected: list[int]) -> None:
    pages = sorted({c["page"] for c in answer.citations})
    row.cited_pages = pages
    if pages:
        row.citation_any = bool(set(pages) & set(expected))
        row.citation_all = set(pages) <= set(expected)


async def run_row(services: AppServices, golden: dict[str, Any], doc_id: str, judge: bool) -> Row:
    row = Row(golden["id"], golden["file"], golden["question"], golden["expected_pages"])
    hits = retrieve(services, row.question, [doc_id])
    row.retrieved_pages = [h.chunk.page_number for h in hits]
    row.recall = any(p in row.expected_pages for p in row.retrieved_pages)
    chunks = [chunk_ref(h.chunk) for h in hits]
    answer, _ = await stream_answer(services, AnswerRequest(row.question, [], chunks))
    row.answer = answer
    score_citations(row, answer, row.expected_pages)
    if judge:
        verdict = await judge_answer(
            services.provider, row.question, golden["reference_answer"], chunks, answer.text
        )
        row.faithfulness = verdict.score
        row.judge_explanation = verdict.explanation
        row.judge_cost = cost_usd(verdict.model, verdict.usage)
    follow = golden.get("follow_up")
    if follow:
        row.follow_up = await run_follow_up(services, doc_id, row, chunks, follow)
    print(
        f"{row.id:8} recall={int(row.recall)} cited={row.cited_pages} exp={row.expected_pages} "
        f"faith={row.faithfulness} {answer.latency_s}s ${answer.usage['cost_usd']:.4f}"
    )
    return row


async def run_follow_up(
    services: AppServices, doc_id: str, row: Row, chunks: list[ChunkRef], follow: dict[str, Any]
) -> dict[str, Any]:
    assert row.answer is not None
    settings = services.settings
    with services.session_factory() as session:
        chat = repo.create_chat(session, None, [doc_id])
        repo.append_exchange(
            session,
            chat.id,
            user={"content": row.question, "chunk_ids": [c.chunk_id for c in sort_chunks(chunks)]},
            assistant={
                "content": row.answer.text,
                "citations": row.answer.citations,
                "usage": row.answer.usage,
                "model": row.answer.usage["model"],
            },
        )
        history: list[HistoryTurn] = load_history(session, chat.id, settings.history_turns)
    question = follow["question"]
    rewritten = await services.provider.rewrite(question, history)
    hits = retrieve(services, rewritten, [doc_id])
    retrieved = [h.chunk.page_number for h in hits]
    answer, _ = await stream_answer(
        services, AnswerRequest(question, history, [chunk_ref(h.chunk) for h in hits])
    )
    cited = sorted({c["page"] for c in answer.citations})
    expected = follow["expected_pages"]
    return {
        "question": question,
        "rewritten_query": rewritten,
        "expected_pages": expected,
        "retrieved_pages": retrieved,
        "recall": any(p in expected for p in retrieved),
        "cited_pages": cited,
        "citation_any": bool(set(cited) & set(expected)) if cited else None,
        "answer": asdict(answer),
        "turn1_cost_usd": row.answer.usage["cost_usd"],
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(p * (len(ordered) - 1))))
    return ordered[k]


def summarise(rows: list[Row]) -> dict[str, Any]:
    answered = [r for r in rows if r.answer]
    with_cites = [r for r in answered if r.cited_pages]
    judged = [r for r in answered if r.faithfulness is not None]
    latencies = [r.answer.latency_s for r in answered if r.answer]
    usages = [r.answer.usage for r in answered if r.answer]
    follow_ups = [r.follow_up for r in rows if r.follow_up]
    mean = lambda xs: round(statistics.fmean(xs), 3) if xs else 0.0  # noqa: E731
    return {
        "questions": len(rows),
        "recall_at_8": mean([float(r.recall) for r in rows]),
        "answers_with_citation": round(len(with_cites) / len(answered), 3) if answered else 0.0,
        "citation_any": mean([float(r.citation_any) for r in with_cites]),
        "citation_all": mean([float(r.citation_all) for r in with_cites]),
        "citation_denominator": len(with_cites),
        "faithfulness_mean": mean([r.faithfulness for r in judged]),
        "faithfulness_distribution": {
            str(s): sum(1 for r in judged if r.faithfulness == s) for s in range(1, 6)
        },
        "judge_failures": len(answered) - len(judged),
        "max_tokens_stops": sum(
            1 for r in answered if r.answer and r.answer.stop_reason == "max_tokens"
        ),
        "latency_median_s": round(statistics.median(latencies), 2) if latencies else 0.0,
        "latency_p95_s": round(percentile(latencies, 0.95), 2),
        "mean_input_tokens": mean(
            [
                u["input_tokens"] + u["cache_read_input_tokens"] + u["cache_creation_input_tokens"]
                for u in usages
            ]
        ),
        "mean_output_tokens": mean([u["output_tokens"] for u in usages]),
        "mean_thinking_tokens": mean([u["thinking_tokens"] for u in usages]),
        "answer_cost_total_usd": round(
            sum(u["cost_usd"] for u in usages)
            + sum(f["answer"]["usage"]["cost_usd"] for f in follow_ups),
            4,
        ),
        "answer_cost_mean_usd": round(mean([u["cost_usd"] for u in usages]), 5),
        "judge_cost_total_usd": round(sum(r.judge_cost for r in rows), 4),
        "follow_up_cache_reads": [
            f["answer"]["usage"]["cache_read_input_tokens"] for f in follow_ups
        ],
    }


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def write_markdown(
    path: Path, settings: Settings, rows: list[Row], summary: dict[str, Any]
) -> None:
    embedder = (
        settings.embedding_model_path
        or f"{settings.embedding_model} @ {settings.embedding_revision[:7]}"
    )
    if settings.embeddings_provider == "fake":
        embedder = "fake (feature hashing, tests only)"
    models = (
        "mock"
        if settings.llm_provider == "mock"
        else f"{settings.answer_model} / {settings.rewrite_model} / {settings.judge_model}"
    )
    lines = [
        "# Eval results",
        "",
        f"Run on {datetime.now(UTC):%Y-%m-%d %H:%M} UTC at commit `{git_sha()}`. Provider: **{settings.llm_provider}**; "
        f"answer / rewrite / judge models: {models}; effort `{settings.answer_effort}`; embedder: {embedder}; "
        f"retrieval top-k vector {settings.top_k_vector} + BM25 {settings.top_k_bm25} -> RRF top {settings.top_k_final}; "
        f"{summary['questions']} questions.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Recall@8 (expected page among retrieved chunks) | {pct(summary['recall_at_8'])} |",
        f"| Answers with at least one citation | {pct(summary['answers_with_citation'])} |",
        f"| Citation accuracy, any cited page correct (n={summary['citation_denominator']}) | {pct(summary['citation_any'])} |",
        f"| Citation accuracy, all cited pages correct (n={summary['citation_denominator']}) | {pct(summary['citation_all'])} |",
        f"| Faithfulness, mean of 1-5 (judge failures: {summary['judge_failures']}) | {summary['faithfulness_mean']:.2f} |",
        f"| Faithfulness distribution 1 / 2 / 3 / 4 / 5 | {' / '.join(str(summary['faithfulness_distribution'][k]) for k in '12345')} |",
        f"| `max_tokens` stops | {summary['max_tokens_stops']} |",
        f"| Latency median / p95 | {summary['latency_median_s']} s / {summary['latency_p95_s']} s |",
        f"| Mean prompt tokens / output tokens / thinking tokens | {summary['mean_input_tokens']:.0f} / {summary['mean_output_tokens']:.0f} / {summary['mean_thinking_tokens']:.0f} |",
        f"| Answer cost, total / mean per question | ${summary['answer_cost_total_usd']:.4f} / ${summary['answer_cost_mean_usd']:.5f} |",
        f"| Judge cost, total | ${summary['judge_cost_total_usd']:.4f} |",
        "",
        "Faithfulness is scored by the judge model from the retrieved excerpts and the reference answer. "
        "With the default configuration Haiku judges Haiku, so treat the score as a consistency check rather than an independent audit.",
        "",
        "## Follow-up turns (query rewrite and prompt caching)",
        "",
        "| # | Follow-up question | Rewritten query | Cache read tokens | Cache write tokens | Cit. any | $ turn 1 | $ turn 2 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        f = r.follow_up
        if not f:
            continue
        u = f["answer"]["usage"]
        lines.append(
            f"| {r.id} | {f['question']} | {f['rewritten_query']} | {u['cache_read_input_tokens']} | {u['cache_creation_input_tokens']} | "
            f"{'-' if f['citation_any'] is None else ('yes' if f['citation_any'] else 'no')} | ${f['turn1_cost_usd']:.4f} | ${u['cost_usd']:.4f} |"
        )
    lines += [
        "",
        "## Per question",
        "",
        "| # | File | Question | Expected | Retrieved pages | Cited pages | Recall@8 | Cit. any | Cit. all | Faith. | s | $ |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        a = r.answer
        yes_no = lambda v: "-" if v is None else ("yes" if v else "no")  # noqa: E731
        lines.append(
            f"| {r.id} | {r.file} | {r.question} | {r.expected_pages} | {r.retrieved_pages} | {r.cited_pages} | "
            f"{yes_no(r.recall)} | {yes_no(r.citation_any)} | {yes_no(r.citation_all)} | {r.faithfulness if r.faithfulness is not None else '-'} | "
            f"{a.latency_s if a else '-'} | {f'{a.usage["cost_usd"]:.4f}' if a else '-'} |"
        )
    lines += [
        "",
        "## How to reproduce",
        "",
        "```bash",
        "cd backend",
        "uv run evals/run.py                                       # real provider, needs ANTHROPIC_API_KEY in the repo-root .env",
        "uv run evals/run.py --provider mock --embeddings fake --limit 3   # offline smoke run",
        "```",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


async def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir) if args.data_dir else Path(tempfile.mkdtemp(prefix="evals-"))
    settings = Settings(
        llm_provider=args.provider, embeddings_provider=args.embeddings, data_dir=data_dir
    )
    services = build_services(settings)
    services.warm_up()
    rows_in = (
        load_golden(Path(args.golden))[: args.limit]
        if args.limit
        else load_golden(Path(args.golden))
    )
    files = list(dict.fromkeys(r["file"] for r in rows_in))
    try:
        ids = ingest_samples(services, files, Path(args.samples))
        rows = [await run_row(services, g, ids[g["file"]], args.judge) for g in rows_in]
        summary = summarise(rows)
        write_markdown(Path(args.out), settings, rows, summary)
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json).write_text(
                json.dumps({"summary": summary, "rows": [asdict(r) for r in rows]}, indent=2),
                encoding="utf-8",
            )
        print(json.dumps(summary, indent=2))
        print(f"wrote {args.out}")
        return 0
    finally:
        services.close()
        if not args.data_dir:
            shutil.rmtree(data_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--provider", choices=["anthropic", "mock"], default="anthropic")
    parser.add_argument("--embeddings", choices=["local", "fake"], default="local")
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN))
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json", default=None, help="also write the raw results as JSON")
    parser.add_argument(
        "--data-dir", default=None, help="reuse a data directory instead of a temp dir"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--judge", dest="judge", action="store_true", default=True)
    parser.add_argument("--no-judge", dest="judge", action="store_false")
    args = parser.parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())

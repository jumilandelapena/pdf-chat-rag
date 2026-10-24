"""Page-bounded chunking.

Chunks never cross a page. Each chunk is a verbatim slice of the page text
(``text == page_text[char_start:char_end]``), holds at most ``target_tokens`` bge WordPiece
tokens and at most ``max_chars`` characters, and consecutive chunks on a page overlap by whole
sentence units adding up to at most ``round(target_tokens * overlap)`` tokens.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.ingest.tokens import count_tokens, token_offsets

PARAGRAPH_RE = re.compile(r"[^\n]+(?:\n[^\n]+)*")
SENTENCE_RE = re.compile(r".+?(?:[.!?][\"')\]]*(?=\s)|$)", re.S)

CountFn = Callable[[str], int]
OffsetsFn = Callable[[str], list[tuple[int, int]]]


@dataclass(frozen=True)
class Chunk:
    page_number: int
    chunk_index: int
    char_start: int
    char_end: int
    text: str
    token_count: int


@dataclass(frozen=True)
class _Unit:
    start: int
    end: int
    tokens: int


def _strip_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _sentence_units(page_text: str, count: CountFn) -> list[_Unit]:
    units: list[_Unit] = []
    for para in PARAGRAPH_RE.finditer(page_text):
        base = para.start()
        for sent in SENTENCE_RE.finditer(para.group(0)):
            start, end = _strip_span(page_text, base + sent.start(), base + sent.end())
            if end > start:
                units.append(_Unit(start, end, count(page_text[start:end])))
    return units


def _split_long_runs(
    page_text: str, units: list[_Unit], max_chars: int, count: CountFn
) -> list[_Unit]:
    """Cut whitespace-free runs longer than ``max_chars`` into fixed-size pieces."""
    out: list[_Unit] = []
    run_re = re.compile(rf"\S{{{max_chars + 1},}}")
    for u in units:
        text = page_text[u.start : u.end]
        if not run_re.search(text):
            out.append(u)
            continue
        pos = 0
        for m in run_re.finditer(text):
            if m.start() > pos:
                s, e = _strip_span(page_text, u.start + pos, u.start + m.start())
                if e > s:
                    out.append(_Unit(s, e, count(page_text[s:e])))
            for k in range(m.start(), m.end(), max_chars):
                s, e = u.start + k, u.start + min(k + max_chars, m.end())
                out.append(_Unit(s, e, count(page_text[s:e])))
            pos = m.end()
        if pos < len(text):
            s, e = _strip_span(page_text, u.start + pos, u.end)
            if e > s:
                out.append(_Unit(s, e, count(page_text[s:e])))
    return out


def _split_unit(
    page_text: str, unit: _Unit, target: int, max_chars: int, count: CountFn, offsets: OffsetsFn
) -> list[_Unit]:
    """Split one oversized unit at token boundaries snapped back to whitespace."""
    if target < 8:
        pieces = []
        for k in range(unit.start, unit.end, max_chars):
            s, e = _strip_span(page_text, k, min(k + max_chars, unit.end))
            if e > s:
                pieces.append(_Unit(s, e, count(page_text[s:e])))
        return pieces
    text = page_text[unit.start : unit.end]
    toks = offsets(text)
    spans: list[tuple[int, int]] = []
    piece_start, n_tok, i = 0, 0, 0
    while i < len(toks):
        ts, te = toks[i]
        if n_tok > 0 and (n_tok + 1 > target or te - piece_start > max_chars):
            cut = ts
            ws = max(text.rfind(" ", piece_start, cut), text.rfind("\n", piece_start, cut))
            if ws > piece_start:
                cut = ws
            spans.append((piece_start, cut))
            piece_start, n_tok = cut, 0
            while i < len(toks) and toks[i][0] < piece_start:
                i += 1
            continue
        n_tok += 1
        i += 1
    spans.append((piece_start, len(text)))
    pieces: list[_Unit] = []
    for rel_s, rel_e in spans:
        s, e = _strip_span(page_text, unit.start + rel_s, unit.start + rel_e)
        if e <= s:
            continue
        piece = _Unit(s, e, count(page_text[s:e]))
        if piece.tokens > target or (e - s) > max_chars:
            pieces.extend(_split_unit(page_text, piece, target - 8, max_chars, count, offsets))
        else:
            pieces.append(piece)
    return pieces


def _pack(
    page_text: str,
    units: list[_Unit],
    target: int,
    overlap_tokens: int,
    max_chars: int,
    count: CountFn,
) -> list[tuple[int, int, str, int]]:
    """Greedy packing with sentence-level overlap. Returns (start, end, text, tokens)."""
    out: list[tuple[int, int, str, int]] = []
    i, prev_j = 0, 0
    while i < len(units):
        j, tok_sum = i, 0
        while j < len(units):
            u = units[j]
            if tok_sum + u.tokens > target or (u.end - units[i].start) > max_chars:
                break
            tok_sum += u.tokens
            j += 1
        if j == i:
            j = i + 1
        if out and j <= prev_j:
            # the overlap window alone would only repeat the previous chunk: drop the overlap
            i = prev_j
            continue
        text = page_text[units[i].start : units[j - 1].end]
        real = count(text)
        while real > target and j - 1 > i:
            j -= 1
            text = page_text[units[i].start : units[j - 1].end]
            real = count(text)
        out.append((units[i].start, units[j - 1].end, text, real))
        prev_j = j
        if j >= len(units):
            break
        s, acc = j, 0
        while s - 1 > i and acc + units[s - 1].tokens <= overlap_tokens:
            acc += units[s - 1].tokens
            s -= 1
        i = s
    return out


def chunk_page(
    page_text: str,
    page_number: int,
    *,
    target_tokens: int = 800,
    overlap: float = 0.15,
    max_chars: int = 4800,
    first_index: int = 0,
    count: CountFn = count_tokens,
    offsets: OffsetsFn = token_offsets,
) -> list[Chunk]:
    if not page_text.strip():
        return []
    units = _split_long_runs(page_text, _sentence_units(page_text, count), max_chars, count)
    sized: list[_Unit] = []
    for u in units:
        if u.tokens > target_tokens or (u.end - u.start) > max_chars:
            sized.extend(_split_unit(page_text, u, target_tokens, max_chars, count, offsets))
        else:
            sized.append(u)
    overlap_tokens = round(target_tokens * overlap)
    packed = _pack(page_text, sized, target_tokens, overlap_tokens, max_chars, count)
    # merge a tiny tail into the previous chunk when the result stays reasonable
    if len(packed) >= 2 and packed[-1][3] < 0.1 * target_tokens:
        start, end = packed[-2][0], packed[-1][1]
        merged = page_text[start:end]
        tokens = count(merged)
        if tokens <= 1.25 * target_tokens and len(merged) <= max_chars:
            packed[-2:] = [(start, end, merged, tokens)]
    return [
        Chunk(page_number, first_index + k, s, e, t, n) for k, (s, e, t, n) in enumerate(packed)
    ]


def chunk_document(pages: Sequence[tuple[int, str]], **kwargs) -> list[Chunk]:
    """Chunk ``(page_number, text)`` pairs with a sequential chunk_index across pages."""
    chunks: list[Chunk] = []
    for page_number, text in pages:
        chunks.extend(chunk_page(text, page_number, first_index=len(chunks), **kwargs))
    return chunks


def sub_windows(text: str, window_tokens: int = 480, max_chars: int = 4800) -> list[str]:
    """Non-overlapping sub-windows of a chunk that fit the embedder's 512-token input limit."""
    windows = [
        c.text
        for c in chunk_page(text, 0, target_tokens=window_tokens, overlap=0, max_chars=max_chars)
    ]
    return windows or [text]

"""Token counting with the vendored bge-small-en-v1.5 WordPiece tokenizer.

The tokenizer is loaded lazily and only once. ``add_special_tokens=False`` so counts describe
the text itself. Note that WordPiece treats any whitespace-free run longer than 100 characters
as a single ``[UNK]`` token, which is why the chunker also bounds characters.
"""

from __future__ import annotations

from pathlib import Path

from tokenizers import Tokenizer

_TOKENIZER: Tokenizer | None = None


def _tokenizer() -> Tokenizer:
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = Tokenizer.from_file(str(Path(__file__).with_name("bge_tokenizer.json")))
    return _TOKENIZER


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_tokenizer().encode(text, add_special_tokens=False).ids)


def token_offsets(text: str) -> list[tuple[int, int]]:
    """Character spans of each token in ``text`` (end exclusive)."""
    if not text:
        return []
    return list(_tokenizer().encode(text, add_special_tokens=False).offsets)

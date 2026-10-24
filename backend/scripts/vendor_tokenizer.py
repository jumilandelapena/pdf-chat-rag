"""One-time helper: copy the bge-small-en-v1.5 tokenizer.json into the app package.

Usage: uv run scripts/vendor_tokenizer.py
The vendored file lets the chunker count tokens offline and without loading torch.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402


def main() -> int:
    from huggingface_hub import hf_hub_download

    settings = Settings(_env_file=None)
    src = hf_hub_download(
        settings.embedding_model, "tokenizer.json", revision=settings.embedding_revision
    )
    dst = Path(__file__).resolve().parents[1] / "app" / "ingest" / "bge_tokenizer.json"
    shutil.copyfile(src, dst)
    digest = hashlib.sha256(dst.read_bytes()).hexdigest()
    print(f"wrote {dst} ({dst.stat().st_size} bytes) sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

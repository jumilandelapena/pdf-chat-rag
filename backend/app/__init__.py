"""pdf-chat-rag backend.

Environment defaults are set here so they apply before any Hugging Face import.
"""

import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

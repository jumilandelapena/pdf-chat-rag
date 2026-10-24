"""Exception types shared across the application."""


class IngestError(Exception):
    """A document could not be ingested (bad file, no text, ...)."""


class PdfError(IngestError):
    """The PDF could not be opened or read."""


class ProviderError(Exception):
    """An LLM provider failed. ``code`` is the SSE error code sent to the client."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

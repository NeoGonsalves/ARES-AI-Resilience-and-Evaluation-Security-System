from dataclasses import dataclass


class ProviderExecutionError(RuntimeError):
    """A safe provider-facing error that never contains provider response bodies or prompts."""


class ProviderNotConfiguredError(ProviderExecutionError):
    pass


@dataclass(frozen=True)
class ProviderResult:
    output_text: str
    token_estimate: int

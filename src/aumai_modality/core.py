"""Core logic for aumai-modality."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from .models import ConversionResult, ModalInput, ModalOutput, Modality

__all__ = [
    "ModalityHandler",
    "TextHandler",
    "StructuredHandler",
    "ModalityConverter",
    "ModalityRouter",
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class ModalityHandler(ABC):
    """Base class for modality-specific processing."""

    @property
    @abstractmethod
    def modality(self) -> Modality:
        """The modality this handler processes."""

    @abstractmethod
    def handle(self, input_data: ModalInput) -> ModalOutput:
        """Process input and return normalized output."""

    @abstractmethod
    def to_text(self, input_data: ModalInput) -> str:
        """Extract a plain-text representation of the input."""

    @abstractmethod
    def from_text(self, text: str) -> ModalOutput:
        """Produce output in this handler's modality from plain text."""


class TextHandler(ModalityHandler):
    """Handler for plain-text modality."""

    @property
    def modality(self) -> Modality:
        return Modality.text

    def handle(self, input_data: ModalInput) -> ModalOutput:
        content = (
            input_data.content.decode("utf-8")
            if isinstance(input_data.content, bytes)
            else input_data.content
        )
        return ModalOutput(
            modality=Modality.text,
            content=content,
            mime_type="text/plain",
        )

    def to_text(self, input_data: ModalInput) -> str:
        content = (
            input_data.content.decode("utf-8")
            if isinstance(input_data.content, bytes)
            else input_data.content
        )
        return str(content)

    def from_text(self, text: str) -> ModalOutput:
        return ModalOutput(
            modality=Modality.text,
            content=text,
            mime_type="text/plain",
        )


class StructuredHandler(ModalityHandler):
    """
    Handler for structured JSON data.

    Converts between free-form text and JSON objects.  When converting
    text -> structured, the text is wrapped in a ``{"text": ...}``
    envelope if it is not already valid JSON.  When converting
    structured -> text, the JSON is pretty-printed.
    """

    @property
    def modality(self) -> Modality:
        return Modality.structured

    def handle(self, input_data: ModalInput) -> ModalOutput:
        raw = (
            input_data.content.decode("utf-8")
            if isinstance(input_data.content, bytes)
            else input_data.content
        )
        # Normalize: ensure the content is valid JSON
        try:
            parsed: Any = json.loads(str(raw))
            serialized = json.dumps(parsed, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, TypeError):
            serialized = json.dumps({"text": str(raw)}, ensure_ascii=False, indent=2)
        return ModalOutput(
            modality=Modality.structured,
            content=serialized,
            mime_type="application/json",
        )

    def to_text(self, input_data: ModalInput) -> str:
        """Serialize structured content to a JSON string."""
        raw = (
            input_data.content.decode("utf-8")
            if isinstance(input_data.content, bytes)
            else str(input_data.content)
        )
        try:
            parsed = json.loads(raw)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, TypeError):
            return raw

    def from_text(self, text: str) -> ModalOutput:
        """Wrap plain text as a JSON object."""
        try:
            parsed: Any = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            parsed = {"text": text}
        return ModalOutput(
            modality=Modality.structured,
            content=json.dumps(parsed, ensure_ascii=False, indent=2),
            mime_type="application/json",
        )


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------

_HANDLER_REGISTRY: dict[Modality, ModalityHandler] = {
    Modality.text: TextHandler(),
    Modality.structured: StructuredHandler(),
}


class ModalityConverter:
    """
    Converts ModalInput between supported modalities.

    The conversion path is:
      source -> text (intermediate) -> target

    For same-modality conversions the handler's ``handle()`` method is
    called directly.
    """

    def __init__(
        self,
        handlers: dict[Modality, ModalityHandler] | None = None,
    ) -> None:
        self._handlers: dict[Modality, ModalityHandler] = (
            dict(handlers) if handlers else dict(_HANDLER_REGISTRY)
        )

    def register_handler(self, handler: ModalityHandler) -> None:
        """Add or replace a modality handler."""
        self._handlers[handler.modality] = handler

    def convert(
        self, input_data: ModalInput, target: Modality
    ) -> ConversionResult:
        """
        Convert *input_data* to *target* modality.

        Raises ``ValueError`` if source or target modality has no handler.
        """
        source = input_data.modality
        source_handler = self._handlers.get(source)
        target_handler = self._handlers.get(target)

        if source_handler is None:
            raise ValueError(
                f"No handler registered for source modality {source.value!r}."
            )
        if target_handler is None:
            raise ValueError(
                f"No handler registered for target modality {target.value!r}."
            )

        if source == target:
            output = source_handler.handle(input_data)
            quality = 1.0
        else:
            # Two-step: source -> text -> target
            intermediate_text = source_handler.to_text(input_data)
            output = target_handler.from_text(intermediate_text)
            # Quality degrades for multi-hop conversions involving binary
            # modalities; text<->structured is lossless.
            quality = _quality_score(source, target)

        return ConversionResult(
            source_modality=source,
            target_modality=target,
            output=output,
            quality_score=quality,
        )

    def supported_modalities(self) -> list[Modality]:
        """Return all modalities with registered handlers."""
        return list(self._handlers.keys())


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ModalityRouter:
    """
    Routes a ModalInput to the appropriate handler.

    Handlers are looked up by modality.
    """

    def __init__(
        self,
        handlers: dict[Modality, ModalityHandler] | None = None,
    ) -> None:
        self._handlers: dict[Modality, ModalityHandler] = (
            dict(handlers) if handlers else dict(_HANDLER_REGISTRY)
        )

    def route(self, input_data: ModalInput) -> ModalOutput:
        """Dispatch *input_data* to its modality handler."""
        handler = self._handlers.get(input_data.modality)
        if handler is None:
            raise ValueError(
                f"No handler registered for modality {input_data.modality.value!r}."
            )
        return handler.handle(input_data)

    def detect(self, raw_content: bytes | str) -> Modality:
        """
        Heuristically detect the modality of *raw_content*.

        Rules (in order):
        1. If it is valid JSON -> structured
        2. Otherwise -> text
        """
        text = (
            raw_content.decode("utf-8", errors="replace")
            if isinstance(raw_content, bytes)
            else raw_content
        )
        stripped = text.strip()
        if stripped and stripped[0] in ("{", "["):
            try:
                json.loads(stripped)
                return Modality.structured
            except (json.JSONDecodeError, ValueError):
                pass
        return Modality.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_QUALITY_MAP: dict[tuple[Modality, Modality], float] = {
    (Modality.text, Modality.structured): 0.95,
    (Modality.structured, Modality.text): 0.95,
    (Modality.text, Modality.text): 1.0,
    (Modality.structured, Modality.structured): 1.0,
}


def _quality_score(source: Modality, target: Modality) -> float:
    """Return an estimated quality score for a conversion pair."""
    return _QUALITY_MAP.get((source, target), 0.5)

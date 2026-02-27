"""aumai-modality quickstart examples.

Run this file directly to verify your installation and see aumai-modality in action:

    python examples/quickstart.py

Each demo function illustrates a different aspect of the library.
"""

from __future__ import annotations

from aumai_modality.core import (
    ModalityConverter,
    ModalityHandler,
    ModalityRouter,
)
from aumai_modality.models import ConversionResult, ModalInput, ModalOutput, Modality


# ---------------------------------------------------------------------------
# Demo 1 — Modality detection from raw content
# ---------------------------------------------------------------------------


def demo_detection() -> None:
    """Use ModalityRouter.detect() to identify modality from raw bytes or str."""
    print("=" * 60)
    print("Demo 1: Modality detection")
    print("=" * 60)

    router = ModalityRouter()

    samples: list[tuple[str, bytes | str]] = [
        ("JSON object",    b'{"event": "login", "user_id": 42}'),
        ("JSON array",     '[1, 2, 3, "four"]'),
        ("Plain text",     "Analyze the quarterly report and summarize findings."),
        ("Invalid JSON",   "{not: valid json"),
        ("Empty string",   ""),
        ("Nested JSON",    b'{"outer": {"inner": [1, 2, 3]}}'),
    ]

    for label, raw in samples:
        detected = router.detect(raw)
        print(f"  {label:20} -> {detected.value}")
    print()


# ---------------------------------------------------------------------------
# Demo 2 — Route an input to its handler
# ---------------------------------------------------------------------------


def demo_routing() -> None:
    """Route ModalInput objects to their registered handlers."""
    print("=" * 60)
    print("Demo 2: Handler routing")
    print("=" * 60)

    router = ModalityRouter()

    inputs = [
        ModalInput(
            modality=Modality.text,
            content="Customer feedback: product is excellent, delivery was fast.",
            mime_type="text/plain",
        ),
        ModalInput(
            modality=Modality.structured,
            content='{"sentiment": "positive", "score": 0.92, "keywords": ["excellent", "fast"]}',
            mime_type="application/json",
        ),
    ]

    for modal_input in inputs:
        output = router.route(modal_input)
        print(f"  Input modality  : {modal_input.modality.value}")
        print(f"  Output modality : {output.modality.value}")
        print(f"  Output MIME     : {output.mime_type}")
        snippet = str(output.content)[:60].replace("\n", " ")
        print(f"  Content snippet : {snippet}")
        print()


# ---------------------------------------------------------------------------
# Demo 3 — Convert between text and structured modalities
# ---------------------------------------------------------------------------


def demo_conversion() -> None:
    """Convert between text and structured modalities in both directions."""
    print("=" * 60)
    print("Demo 3: Modality conversion")
    print("=" * 60)

    converter = ModalityConverter()

    # Text -> Structured
    text_input = ModalInput(
        modality=Modality.text,
        content="User intent: schedule a meeting for tomorrow at 3pm.",
    )
    text_to_struct = converter.convert(text_input, target=Modality.structured)
    _print_result("text -> structured", text_to_struct)

    # Structured -> Text (valid JSON input)
    struct_input = ModalInput(
        modality=Modality.structured,
        content='{"intent": "schedule_meeting", "time": "tomorrow 3pm", "priority": "high"}',
    )
    struct_to_text = converter.convert(struct_input, target=Modality.text)
    _print_result("structured -> text", struct_to_text)

    # Same modality (normalization)
    already_json = ModalInput(
        modality=Modality.structured,
        content='{"name":"Alice","score":99}',  # no indentation
    )
    normalized = converter.convert(already_json, target=Modality.structured)
    _print_result("structured -> structured (normalize)", normalized)


# ---------------------------------------------------------------------------
# Demo 4 — Custom handler registration (voice stub)
# ---------------------------------------------------------------------------


def demo_custom_handler() -> None:
    """Register a stub VoiceHandler and use it in conversion."""
    print("=" * 60)
    print("Demo 4: Custom handler registration (voice stub)")
    print("=" * 60)

    class StubVoiceHandler(ModalityHandler):
        """Stub — replace _transcribe and _synthesize with real ASR/TTS."""

        @property
        def modality(self) -> Modality:
            return Modality.voice

        def handle(self, input_data: ModalInput) -> ModalOutput:
            return ModalOutput(
                modality=Modality.voice,
                content=self._transcribe(input_data.content),
                mime_type="text/plain",
            )

        def to_text(self, input_data: ModalInput) -> str:
            return self._transcribe(input_data.content)

        def from_text(self, text: str) -> ModalOutput:
            return ModalOutput(
                modality=Modality.voice,
                content=f"[synthesized audio: {text[:40]}]".encode(),
                mime_type="audio/wav",
            )

        def _transcribe(self, content: bytes | str) -> str:
            # Real implementation: call Whisper or cloud ASR
            return "Hello, I need help with my account."

    converter = ModalityConverter()
    converter.register_handler(StubVoiceHandler())

    supported = converter.supported_modalities()
    print(f"  Supported modalities: {[m.value for m in supported]}")

    voice_input = ModalInput(
        modality=Modality.voice,
        content=b"<raw audio bytes placeholder>",
        mime_type="audio/wav",
    )

    # Voice -> text
    result = converter.convert(voice_input, target=Modality.text)
    _print_result("voice -> text", result)

    # Voice -> structured
    result = converter.convert(voice_input, target=Modality.structured)
    _print_result("voice -> structured", result)


# ---------------------------------------------------------------------------
# Demo 5 — Modality-agnostic input pipeline
# ---------------------------------------------------------------------------


def demo_agnostic_pipeline() -> None:
    """Normalize any supported input to plain text automatically."""
    print("=" * 60)
    print("Demo 5: Modality-agnostic normalization pipeline")
    print("=" * 60)

    router = ModalityRouter()
    converter = ModalityConverter()

    def normalize_to_text(raw: bytes | str) -> str:
        """Detect, route, and convert any input to plain text."""
        detected = router.detect(raw)
        modal_input = ModalInput(modality=detected, content=raw)
        result = converter.convert(modal_input, target=Modality.text)
        content = result.output.content
        return content if isinstance(content, str) else content.decode("utf-8")

    test_inputs: list[bytes | str] = [
        "Simple plain text from a user message.",
        b'{"action": "create_ticket", "title": "Login button broken", "priority": 1}',
        '[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]',
        "   ",  # whitespace only — detected as text
    ]

    for raw in test_inputs:
        label = repr(raw)[:50]
        normalized = normalize_to_text(raw)
        print(f"  Input   : {label}")
        print(f"  Output  : {normalized[:70].replace(chr(10), ' ')}")
        print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_result(label: str, result: ConversionResult) -> None:
    content_str = (
        result.output.content
        if isinstance(result.output.content, str)
        else result.output.content.decode("utf-8", errors="replace")
    )
    snippet = content_str[:80].replace("\n", " ")
    print(f"  [{label}]")
    print(f"    quality={result.quality_score:.2f}  "
          f"mime={result.output.mime_type}")
    print(f"    content : {snippet}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all quickstart demos in sequence."""
    demo_detection()
    demo_routing()
    demo_conversion()
    demo_custom_handler()
    demo_agnostic_pipeline()
    print("All demos completed successfully.")


if __name__ == "__main__":
    main()

# Getting Started with aumai-modality

This guide walks you from a fresh install to processing, routing, and converting modal
inputs in under five minutes.

---

## Prerequisites

- Python 3.11 or later
- `pip` (any recent version)

No external services, API keys, ML models, or database connections are required.
The built-in text and structured handlers run entirely in-process with no heavy dependencies.

---

## Installation

### From PyPI (recommended)

```bash
pip install aumai-modality
```

### From source

```bash
git clone https://github.com/aumai/aumai-modality
cd aumai-modality
pip install -e ".[dev]"
```

### Verify the installation

```bash
aumai-modality --version
# aumai-modality, version 0.1.0

python -c "from aumai_modality.core import ModalityRouter; print('OK')"
# OK
```

---

## Step-by-Step Tutorial

### Step 1 — Understand the three core concepts

Before writing any code, understand what the three main objects do:

- **`ModalInput`** — a payload with a known modality, content (bytes or str), MIME type, and optional metadata.
- **`ModalityRouter`** — dispatches a `ModalInput` to the correct handler for processing. Also detects modality from raw bytes.
- **`ModalityConverter`** — converts a `ModalInput` from one modality to another, returning a `ConversionResult` with a quality score.

### Step 2 — Create a ModalInput

```python
from aumai_modality.models import ModalInput, Modality

# Text input
text_input = ModalInput(
    modality=Modality.text,
    content="The quarterly revenue exceeded expectations by 18%.",
    mime_type="text/plain",
)

# Structured JSON input
structured_input = ModalInput(
    modality=Modality.structured,
    content='{"revenue_delta": 0.18, "period": "Q3"}',
    mime_type="application/json",
)
```

### Step 3 — Route an input to its handler

`ModalityRouter` finds the handler registered for the input's modality and returns a
normalized `ModalOutput`.

```python
from aumai_modality.core import ModalityRouter

router = ModalityRouter()

output = router.route(text_input)
print(output.modality)   # Modality.text
print(output.mime_type)  # "text/plain"
print(output.content)    # "The quarterly revenue exceeded expectations by 18%."
```

### Step 4 — Detect modality from raw content

When you receive raw bytes from an external source and do not know the modality in advance,
use `detect()`.

```python
raw_json = b'{"event": "user_login", "user_id": 42}'
detected = router.detect(raw_json)
print(detected)  # Modality.structured

raw_text = b"Hello from the agent."
detected = router.detect(raw_text)
print(detected)  # Modality.text

# Detection works on str as well as bytes
detected = router.detect('{"nested": {"key": "val"}}')
print(detected)  # Modality.structured
```

### Step 5 — Convert between modalities

`ModalityConverter` converts any `ModalInput` to a target modality via a text-intermediate
path.

```python
from aumai_modality.core import ModalityConverter
from aumai_modality.models import Modality

converter = ModalityConverter()

# Convert plain text to structured JSON
result = converter.convert(text_input, target=Modality.structured)
print(result.output.content)
# {
#   "text": "The quarterly revenue exceeded expectations by 18%."
# }
print(result.quality_score)  # 0.95

# Convert structured JSON to plain text
result = converter.convert(structured_input, target=Modality.text)
print(result.output.content)
# {
#   "revenue_delta": 0.18,
#   "period": "Q3"
# }
print(result.quality_score)  # 0.95
```

### Step 6 — Inspect a ConversionResult

```python
result = converter.convert(text_input, target=Modality.structured)

print(f"Source modality : {result.source_modality.value}")
print(f"Target modality : {result.target_modality.value}")
print(f"Quality score   : {result.quality_score}")
print(f"Output MIME     : {result.output.mime_type}")
print(f"Output content  : {result.output.content[:80]}")
```

### Step 7 — Use the CLI

```bash
# Write some JSON to a file
echo '{"name": "Alice", "score": 99}' > data.json

# Detect its modality
aumai-modality detect --input data.json
# Detected modality: structured

# Convert to plain text
aumai-modality convert --input data.json --target text
# {
#   "name": "Alice",
#   "score": 99
# }

# Write a text file and convert to structured JSON
echo "User query: find all open support tickets" > query.txt
aumai-modality convert --input query.txt --target structured --output query.json
cat query.json
# {
#   "text": "User query: find all open support tickets"
# }
```

---

## Common Patterns and Recipes

### Pattern 1 — Build a modality-agnostic input pipeline

When building an agent that must handle inputs from multiple sources (API, voice, file),
use `detect()` followed by `route()` to normalize everything to a single output format.

```python
from aumai_modality.core import ModalityConverter, ModalityRouter
from aumai_modality.models import ModalInput, Modality


def normalize_to_text(raw_content: bytes | str) -> str:
    """Accept any supported input and return a plain text string."""
    router = ModalityRouter()
    converter = ModalityConverter()

    detected = router.detect(raw_content)
    modal_input = ModalInput(modality=detected, content=raw_content)
    result = converter.convert(modal_input, target=Modality.text)

    content = result.output.content
    return content if isinstance(content, str) else content.decode("utf-8")


# Works with raw JSON bytes
text1 = normalize_to_text(b'{"status": "ok", "count": 3}')
print(text1)

# Works with plain text
text2 = normalize_to_text("Just a regular string from the user.")
print(text2)
```

### Pattern 2 — Convert agent output to a target modality before handoff

When handing off to a downstream agent that expects JSON, convert the current output.

```python
from aumai_modality.core import ModalityConverter
from aumai_modality.models import ModalInput, Modality

converter = ModalityConverter()

# Upstream agent produced plain text
agent_output = "Customer satisfaction score: 8.2 out of 10. Trend: improving."

modal_input = ModalInput(modality=Modality.text, content=agent_output)
result = converter.convert(modal_input, target=Modality.structured)

# Pass result.output.content as the context in a HandoffRequest
print(result.output.content)
# {
#   "text": "Customer satisfaction score: 8.2 out of 10. Trend: improving."
# }
```

### Pattern 3 — Implement and register a custom VoiceHandler

For voice modality, subclass `ModalityHandler` and register it.

```python
from aumai_modality.core import ModalityConverter, ModalityHandler, ModalityRouter
from aumai_modality.models import ModalInput, ModalOutput, Modality


class StubVoiceHandler(ModalityHandler):
    """Stub implementation — replace with real ASR/TTS in production."""

    @property
    def modality(self) -> Modality:
        return Modality.voice

    def handle(self, input_data: ModalInput) -> ModalOutput:
        return ModalOutput(
            modality=Modality.voice,
            content="[transcribed text from voice input]",
            mime_type="text/plain",
        )

    def to_text(self, input_data: ModalInput) -> str:
        return "[transcribed text from voice input]"

    def from_text(self, text: str) -> ModalOutput:
        return ModalOutput(
            modality=Modality.voice,
            content=f"[synthesized audio for: {text[:40]}]".encode("utf-8"),
            mime_type="audio/wav",
        )


# Register in both router and converter
router = ModalityRouter()
converter = ModalityConverter()
handler = StubVoiceHandler()
router._handlers[Modality.voice] = handler
converter.register_handler(handler)

# Now voice modality works end-to-end
voice_input = ModalInput(modality=Modality.voice, content=b"<raw audio>")
output = router.route(voice_input)
print(output.content)  # "[transcribed text from voice input]"

result = converter.convert(voice_input, target=Modality.structured)
print(result.output.content)
```

### Pattern 4 — Validate that a conversion meets a quality threshold

Before passing converted content to a downstream agent, check the quality score.

```python
MINIMUM_QUALITY = 0.9

result = converter.convert(some_input, target=Modality.structured)
if result.quality_score < MINIMUM_QUALITY:
    raise RuntimeError(
        f"Conversion quality {result.quality_score:.2f} is below threshold "
        f"{MINIMUM_QUALITY}. Cannot proceed."
    )
```

### Pattern 5 — Pass bytes content (e.g., from reading a file)

Handlers accept both `bytes` and `str`. When reading files, pass bytes directly.

```python
from pathlib import Path
from aumai_modality.models import ModalInput, Modality
from aumai_modality.core import ModalityRouter

raw_bytes = Path("report.json").read_bytes()
router = ModalityRouter()
detected = router.detect(raw_bytes)

modal_input = ModalInput(
    modality=detected,
    content=raw_bytes,
    mime_type="application/json",
)
output = router.route(modal_input)
```

---

## Troubleshooting FAQ

**Q: `ValueError: No handler registered for source modality 'voice'.`**

A: The default `ModalityConverter` only has handlers for `text` and `structured`.
For `voice`, `image`, and `video`, you must implement and register a `ModalityHandler`
subclass. See Pattern 3 above.

---

**Q: My JSON input is not being detected as `structured` — it comes back as `text`.**

A: `detect()` strips whitespace and checks whether the first character is `{` or `[`
before attempting to parse. Ensure the content is valid JSON that starts with one of
those characters. A JSON string like `"hello"` starts with `"` and will be classified
as text.

---

**Q: The converted output is `{"text": "..."}` — I expected the original JSON.**

A: This is the `StructuredHandler`'s graceful degradation behavior. If the input is
not already valid JSON when going from `text` to `structured`, the handler wraps it in
a `{"text": ...}` envelope. If your input is already valid JSON, set the source
modality to `Modality.structured` (or let `detect()` identify it) so that the
`StructuredHandler` parses and re-serializes it directly.

---

**Q: The quality score is `0.5` for my conversion.**

A: A quality score of `0.5` means the conversion pair `(source, target)` is not in
the built-in quality map. This happens for novel modality pairs involving custom
handlers (e.g., `voice` → `structured`). Override the quality map by subclassing
`ModalityConverter` or by post-processing the `ConversionResult` with your own scoring.

---

**Q: Can I use `ModalityRouter` and `ModalityConverter` with the same custom handlers?**

A: Yes, but you must register the handler in both separately. They each maintain their
own `_handlers` dict. See Pattern 3 above for the recommended approach.

---

**Q: The CLI says `Error: No handler registered for...` but I registered a handler in Python.**

A: The CLI creates its own `ModalityRouter` and `ModalityConverter` instances. Custom
handlers registered in Python code are not automatically available to the CLI. For the
CLI to use custom handlers, you would need to extend the CLI code itself.

---

## Next Steps

- Read the [API Reference](api-reference.md) for complete class and method documentation.
- Explore the [examples/](../examples/) directory for runnable demos.
- See [CONTRIBUTING.md](../CONTRIBUTING.md) to contribute new handler implementations.

# API Reference — aumai-modality

Full reference for all public classes, functions, and Pydantic models exposed by
`aumai-modality`. Everything documented here is exported from `aumai_modality.core` or
`aumai_modality.models`.

---

## Module: `aumai_modality.models`

All data structures are Pydantic v2 `BaseModel` subclasses unless noted otherwise.

---

### `Modality`

```python
class Modality(str, Enum):
    text       = "text"
    voice      = "voice"
    image      = "image"
    video      = "video"
    structured = "structured"
```

Enum representing all supported interaction modalities.

| Value | Handler available? | Description |
|---|---|---|
| `text` | Yes (built-in) | Plain text content. MIME: `text/plain`. |
| `structured` | Yes (built-in) | JSON-structured data. MIME: `application/json`. |
| `voice` | No (plug-in slot) | Audio content (speech). MIME: `audio/wav`, `audio/mpeg`, etc. |
| `image` | No (plug-in slot) | Image content. MIME: `image/png`, `image/jpeg`, etc. |
| `video` | No (plug-in slot) | Video content. MIME: `video/mp4`, etc. |

**Notes:**
- `Modality` is a `str` subclass. `Modality.text == "text"` is `True`.
- Only `text` and `structured` have built-in handlers. `voice`, `image`, and `video` require
  custom `ModalityHandler` implementations to be registered.

**Example:**

```python
from aumai_modality.models import Modality

m = Modality.structured
print(m.value)           # "structured"
print(m == "structured") # True
```

---

### `ModalInput`

```python
class ModalInput(BaseModel):
    modality: Modality
    content: bytes | str
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = {}
```

An input payload in a specific modality. The entry point for all routing and conversion
operations.

**Fields:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `modality` | `Modality` | Yes | — | The declared modality of the content. |
| `content` | `bytes \| str` | Yes | — | The raw payload. Handlers accept both; bytes are decoded as UTF-8. |
| `mime_type` | `str` | No | `"text/plain"` | MIME type hint. Does not affect processing logic but is passed through to handlers and can be read by downstream code. |
| `metadata` | `dict[str, Any]` | No | `{}` | Arbitrary caller-provided metadata (e.g., source, timestamp, language code). Not processed by built-in handlers. |

**Example:**

```python
from aumai_modality.models import ModalInput, Modality

# From a plain text string
text_input = ModalInput(
    modality=Modality.text,
    content="Analyze the following customer feedback.",
    mime_type="text/plain",
    metadata={"source": "zendesk", "ticket_id": "TKT-1234"},
)

# From raw bytes read from a file
json_bytes = b'{"event": "purchase", "amount": 149.99}'
json_input = ModalInput(
    modality=Modality.structured,
    content=json_bytes,
    mime_type="application/json",
)
```

---

### `ModalOutput`

```python
class ModalOutput(BaseModel):
    modality: Modality
    content: bytes | str
    mime_type: str = "text/plain"
```

An output payload produced by a handler or converter.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `modality` | `Modality` | The modality of the output content. |
| `content` | `bytes \| str` | The processed output. Built-in handlers always return `str`; custom handlers may return `bytes`. |
| `mime_type` | `str` | MIME type of the output. Set by each handler. `TextHandler` → `"text/plain"`, `StructuredHandler` → `"application/json"`. |

---

### `ConversionResult`

```python
class ConversionResult(BaseModel):
    source_modality: Modality
    target_modality: Modality
    output: ModalOutput
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
```

The result of a modality conversion operation, returned by `ModalityConverter.convert()`.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `source_modality` | `Modality` | The modality of the input that was converted. |
| `target_modality` | `Modality` | The modality of the produced output. |
| `output` | `ModalOutput` | The converted output payload. |
| `quality_score` | `float` | Estimated fidelity of the conversion: `1.0` = lossless, `0.0` = total loss. |

**Quality score values:**

| Conversion pair | Score | Reason |
|---|---|---|
| Same modality (any) | `1.0` | Direct pass-through via `handle()` |
| `text` → `structured` | `0.95` | Near-lossless; non-JSON text wrapped in envelope |
| `structured` → `text` | `0.95` | Near-lossless; JSON pretty-printed |
| Any other pair | `0.5` | Unknown fidelity for unregistered conversion paths |

---

## Module: `aumai_modality.core`

---

### `ModalityHandler` (abstract base class)

```python
from abc import ABC, abstractmethod

class ModalityHandler(ABC):
    @property
    @abstractmethod
    def modality(self) -> Modality: ...

    @abstractmethod
    def handle(self, input_data: ModalInput) -> ModalOutput: ...

    @abstractmethod
    def to_text(self, input_data: ModalInput) -> str: ...

    @abstractmethod
    def from_text(self, text: str) -> ModalOutput: ...
```

Abstract base class for all modality handlers. Subclass this to add support for new
modalities (voice, image, video, or custom types).

**Abstract properties and methods:**

#### `ModalityHandler.modality` (property)

```python
@property
@abstractmethod
def modality(self) -> Modality
```

The modality this handler processes. Must return a `Modality` enum value.

#### `ModalityHandler.handle`

```python
@abstractmethod
def handle(self, input_data: ModalInput) -> ModalOutput
```

Process an input and return a normalized output in the same modality.

- **Parameters:** `input_data` — the `ModalInput` to process.
- **Returns:** `ModalOutput` — the processed output.
- **Notes:** Used for same-modality conversions (normalization). Also called by `ModalityRouter.route()`.

#### `ModalityHandler.to_text`

```python
@abstractmethod
def to_text(self, input_data: ModalInput) -> str
```

Extract a plain-text representation of the input. Used as the intermediate step in
cross-modality conversions.

- **Parameters:** `input_data` — the `ModalInput` to extract text from.
- **Returns:** `str` — a plain text representation.

#### `ModalityHandler.from_text`

```python
@abstractmethod
def from_text(self, text: str) -> ModalOutput
```

Produce an output in this handler's modality from a plain text string. Used as the
final step in cross-modality conversions.

- **Parameters:** `text` — plain text to convert into this modality.
- **Returns:** `ModalOutput` — output in this handler's modality.

**Custom handler example:**

```python
from aumai_modality.core import ModalityHandler
from aumai_modality.models import ModalInput, ModalOutput, Modality


class VoiceHandler(ModalityHandler):
    @property
    def modality(self) -> Modality:
        return Modality.voice

    def handle(self, input_data: ModalInput) -> ModalOutput:
        transcript = self._transcribe(input_data.content)
        return ModalOutput(modality=Modality.voice, content=transcript,
                           mime_type="text/plain")

    def to_text(self, input_data: ModalInput) -> str:
        return self._transcribe(input_data.content)

    def from_text(self, text: str) -> ModalOutput:
        audio_bytes = self._synthesize(text)
        return ModalOutput(modality=Modality.voice, content=audio_bytes,
                           mime_type="audio/wav")

    def _transcribe(self, content: bytes | str) -> str:
        # Integrate with Whisper or similar ASR service
        return "[transcription]"

    def _synthesize(self, text: str) -> bytes:
        # Integrate with a TTS service
        return b"[audio bytes]"
```

---

### `TextHandler`

```python
class TextHandler(ModalityHandler):
    @property
    def modality(self) -> Modality:
        return Modality.text
```

Built-in handler for plain-text content. Registered by default in both
`ModalityRouter` and `ModalityConverter`.

#### `TextHandler.handle`

Decodes bytes content to UTF-8 str and returns a `ModalOutput` with `mime_type="text/plain"`.

#### `TextHandler.to_text`

Returns the content as a plain string (decoding bytes if necessary).

#### `TextHandler.from_text`

Returns a `ModalOutput` with `modality=Modality.text`, `content=text`, `mime_type="text/plain"`.

---

### `StructuredHandler`

```python
class StructuredHandler(ModalityHandler):
    @property
    def modality(self) -> Modality:
        return Modality.structured
```

Built-in handler for structured JSON content. Registered by default in both
`ModalityRouter` and `ModalityConverter`.

#### `StructuredHandler.handle`

Normalizes JSON content:
- If the raw content is valid JSON: parses and re-serializes with `indent=2`, `ensure_ascii=False`.
- If the raw content is not valid JSON: wraps it in `{"text": "<content>"}` and serializes.

Returns `ModalOutput` with `mime_type="application/json"`.

#### `StructuredHandler.to_text`

Serializes structured content to a pretty-printed JSON string. Returns the raw string if
JSON parsing fails.

#### `StructuredHandler.from_text`

Converts plain text to a structured JSON output:
- If `text` is already valid JSON: parses and re-serializes.
- Otherwise: wraps as `{"text": text}`.

Returns `ModalOutput` with `mime_type="application/json"`.

---

### `ModalityConverter`

```python
class ModalityConverter:
    def __init__(
        self,
        handlers: dict[Modality, ModalityHandler] | None = None,
    ) -> None: ...
```

Converts `ModalInput` between supported modalities. The default instance has handlers
for `text` and `structured`.

- **Parameters:**
  - `handlers` — optional dict overriding the built-in handler registry. If `None`,
    uses the module-level `_HANDLER_REGISTRY` containing `TextHandler` and `StructuredHandler`.

#### `ModalityConverter.register_handler`

```python
def register_handler(self, handler: ModalityHandler) -> None
```

Add or replace a modality handler.

- **Parameters:**
  - `handler` — a `ModalityHandler` instance.
- **Returns:** `None`
- **Side effects:** Registers `handler` under `handler.modality`, replacing any existing handler for that modality.

#### `ModalityConverter.convert`

```python
def convert(self, input_data: ModalInput, target: Modality) -> ConversionResult
```

Convert `input_data` to the `target` modality.

- **Parameters:**
  - `input_data` — the `ModalInput` to convert.
  - `target` — the desired output `Modality`.
- **Returns:** `ConversionResult` — with the converted `ModalOutput` and a `quality_score`.
- **Raises:**
  - `ValueError` — if the source modality has no registered handler.
  - `ValueError` — if the target modality has no registered handler.
- **Algorithm:**
  1. If `source == target`: call `source_handler.handle(input_data)`, quality `1.0`.
  2. Otherwise: `intermediate_text = source_handler.to_text(input_data)`, then `output = target_handler.from_text(intermediate_text)`, quality from `_quality_score(source, target)`.

**Example:**

```python
converter = ModalityConverter()

result = converter.convert(
    ModalInput(modality=Modality.text, content="hello world"),
    target=Modality.structured,
)
assert result.source_modality == Modality.text
assert result.target_modality == Modality.structured
assert result.quality_score == 0.95
assert '"text"' in result.output.content
```

#### `ModalityConverter.supported_modalities`

```python
def supported_modalities(self) -> list[Modality]
```

Return all modalities with registered handlers.

- **Returns:** `list[Modality]` — the keys of the internal handler registry.

---

### `ModalityRouter`

```python
class ModalityRouter:
    def __init__(
        self,
        handlers: dict[Modality, ModalityHandler] | None = None,
    ) -> None: ...
```

Routes a `ModalInput` to the appropriate handler. Also provides heuristic modality
detection from raw content.

- **Parameters:**
  - `handlers` — optional dict overriding the built-in handler registry.

#### `ModalityRouter.route`

```python
def route(self, input_data: ModalInput) -> ModalOutput
```

Dispatch `input_data` to its registered modality handler.

- **Parameters:**
  - `input_data` — the `ModalInput` to dispatch.
- **Returns:** `ModalOutput` — the handler's processed output.
- **Raises:** `ValueError` — if `input_data.modality` has no registered handler.

**Example:**

```python
router = ModalityRouter()
output = router.route(ModalInput(modality=Modality.text, content="hi"))
assert output.modality == Modality.text
assert output.content == "hi"
```

#### `ModalityRouter.detect`

```python
def detect(self, raw_content: bytes | str) -> Modality
```

Heuristically detect the modality of raw content.

- **Parameters:**
  - `raw_content` — raw bytes or str. Bytes are decoded as UTF-8 (with `errors="replace"`).
- **Returns:** `Modality` — the detected modality.
- **Algorithm:**
  1. Strip whitespace from the decoded text.
  2. If the first character is `{` or `[`: attempt `json.loads()`.
  3. If parsing succeeds: return `Modality.structured`.
  4. Otherwise: return `Modality.text`.
- **Notes:** Only detects `text` and `structured`. Voice, image, and video content cannot be auto-detected by this heuristic — they require the caller to specify the modality explicitly.

**Example:**

```python
router = ModalityRouter()

assert router.detect('{"key": "val"}') == Modality.structured
assert router.detect("[1, 2, 3]")       == Modality.structured
assert router.detect("plain text")      == Modality.text
assert router.detect("{not valid json") == Modality.text
assert router.detect(b'{"x": 1}')       == Modality.structured
```

---

## Module-level helpers

### `_HANDLER_REGISTRY`

```python
_HANDLER_REGISTRY: dict[Modality, ModalityHandler] = {
    Modality.text: TextHandler(),
    Modality.structured: StructuredHandler(),
}
```

The default handler registry shared as the initialization source for both
`ModalityConverter` and `ModalityRouter`. Direct mutation of this dict is not recommended;
use `register_handler()` on your instance instead.

---

### `_quality_score`

```python
def _quality_score(source: Modality, target: Modality) -> float
```

Return an estimated quality score for a conversion pair.

- **Parameters:**
  - `source` — source `Modality`.
  - `target` — target `Modality`.
- **Returns:** `float` — quality score from the `_QUALITY_MAP`, or `0.5` if the pair is not in the map.

**Quality map:**

```python
_QUALITY_MAP = {
    (Modality.text,       Modality.structured): 0.95,
    (Modality.structured, Modality.text):       0.95,
    (Modality.text,       Modality.text):       1.0,
    (Modality.structured, Modality.structured): 1.0,
}
```

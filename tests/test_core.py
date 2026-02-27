"""Tests for aumai-modality core module."""

from __future__ import annotations

import json

import pytest

from aumai_modality.core import (
    ModalityConverter,
    ModalityRouter,
    StructuredHandler,
    TextHandler,
    _quality_score,
)
from aumai_modality.models import ConversionResult, ModalInput, ModalOutput, Modality


# ---------------------------------------------------------------------------
# TextHandler tests
# ---------------------------------------------------------------------------


class TestTextHandler:
    def test_modality_property(self, text_handler: TextHandler) -> None:
        assert text_handler.modality == Modality.text

    def test_handle_string_content(
        self, text_handler: TextHandler, text_input: ModalInput
    ) -> None:
        output = text_handler.handle(text_input)
        assert isinstance(output, ModalOutput)
        assert output.modality == Modality.text
        assert output.mime_type == "text/plain"
        assert "plain text content" in str(output.content)

    def test_handle_bytes_content(
        self, text_handler: TextHandler, text_bytes_input: ModalInput
    ) -> None:
        output = text_handler.handle(text_bytes_input)
        assert isinstance(output.content, str)
        assert "Binary" in output.content

    def test_to_text_string(
        self, text_handler: TextHandler, text_input: ModalInput
    ) -> None:
        text = text_handler.to_text(text_input)
        assert isinstance(text, str)
        assert "plain text content" in text

    def test_to_text_bytes(
        self, text_handler: TextHandler, text_bytes_input: ModalInput
    ) -> None:
        text = text_handler.to_text(text_bytes_input)
        assert isinstance(text, str)
        assert "Binary" in text

    def test_from_text_returns_text_output(
        self, text_handler: TextHandler
    ) -> None:
        output = text_handler.from_text("Hello world")
        assert output.modality == Modality.text
        assert output.content == "Hello world"
        assert output.mime_type == "text/plain"

    def test_from_text_empty_string(
        self, text_handler: TextHandler
    ) -> None:
        output = text_handler.from_text("")
        assert output.content == ""


# ---------------------------------------------------------------------------
# StructuredHandler tests
# ---------------------------------------------------------------------------


class TestStructuredHandler:
    def test_modality_property(
        self, structured_handler: StructuredHandler
    ) -> None:
        assert structured_handler.modality == Modality.structured

    def test_handle_valid_json_string(
        self,
        structured_handler: StructuredHandler,
        structured_input: ModalInput,
    ) -> None:
        output = structured_handler.handle(structured_input)
        assert output.modality == Modality.structured
        assert output.mime_type == "application/json"
        parsed = json.loads(str(output.content))
        assert parsed["name"] == "Alice"

    def test_handle_bytes_content(
        self,
        structured_handler: StructuredHandler,
        structured_bytes_input: ModalInput,
    ) -> None:
        output = structured_handler.handle(structured_bytes_input)
        parsed = json.loads(str(output.content))
        assert parsed["key"] == "value"

    def test_handle_invalid_json_wraps_in_text_envelope(
        self, structured_handler: StructuredHandler
    ) -> None:
        invalid = ModalInput(
            modality=Modality.structured,
            content="not valid json at all",
        )
        output = structured_handler.handle(invalid)
        parsed = json.loads(str(output.content))
        assert "text" in parsed
        assert "not valid json" in parsed["text"]

    def test_to_text_returns_formatted_json(
        self,
        structured_handler: StructuredHandler,
        structured_input: ModalInput,
    ) -> None:
        text = structured_handler.to_text(structured_input)
        parsed = json.loads(text)
        assert parsed["name"] == "Alice"

    def test_to_text_invalid_json_returns_raw(
        self, structured_handler: StructuredHandler
    ) -> None:
        raw_input = ModalInput(
            modality=Modality.structured,
            content="not json",
        )
        text = structured_handler.to_text(raw_input)
        assert text == "not json"

    def test_from_text_valid_json(
        self, structured_handler: StructuredHandler
    ) -> None:
        output = structured_handler.from_text('{"x": 1}')
        parsed = json.loads(str(output.content))
        assert parsed["x"] == 1
        assert output.mime_type == "application/json"

    def test_from_text_plain_text_wraps(
        self, structured_handler: StructuredHandler
    ) -> None:
        output = structured_handler.from_text("just a sentence")
        parsed = json.loads(str(output.content))
        assert parsed["text"] == "just a sentence"

    def test_from_text_empty_string_wraps(
        self, structured_handler: StructuredHandler
    ) -> None:
        output = structured_handler.from_text("")
        parsed = json.loads(str(output.content))
        assert "text" in parsed


# ---------------------------------------------------------------------------
# ModalityConverter tests
# ---------------------------------------------------------------------------


class TestModalityConverter:
    def test_supported_modalities_includes_text_and_structured(
        self, converter: ModalityConverter
    ) -> None:
        supported = converter.supported_modalities()
        assert Modality.text in supported
        assert Modality.structured in supported

    def test_same_modality_conversion_text(
        self, converter: ModalityConverter, text_input: ModalInput
    ) -> None:
        result = converter.convert(text_input, Modality.text)
        assert isinstance(result, ConversionResult)
        assert result.source_modality == Modality.text
        assert result.target_modality == Modality.text
        assert result.quality_score == 1.0

    def test_same_modality_conversion_structured(
        self,
        converter: ModalityConverter,
        structured_input: ModalInput,
    ) -> None:
        result = converter.convert(structured_input, Modality.structured)
        assert result.quality_score == 1.0

    def test_text_to_structured_conversion(
        self, converter: ModalityConverter, text_input: ModalInput
    ) -> None:
        result = converter.convert(text_input, Modality.structured)
        assert result.source_modality == Modality.text
        assert result.target_modality == Modality.structured
        assert result.quality_score == pytest.approx(0.95)
        parsed = json.loads(str(result.output.content))
        assert isinstance(parsed, dict)

    def test_structured_to_text_conversion(
        self,
        converter: ModalityConverter,
        structured_input: ModalInput,
    ) -> None:
        result = converter.convert(structured_input, Modality.text)
        assert result.source_modality == Modality.structured
        assert result.target_modality == Modality.text
        assert result.quality_score == pytest.approx(0.95)

    def test_no_source_handler_raises(
        self, converter: ModalityConverter
    ) -> None:
        unknown_input = ModalInput(
            modality=Modality.voice,
            content=b"\x00\x01",
        )
        with pytest.raises(ValueError, match="No handler registered for source"):
            converter.convert(unknown_input, Modality.text)

    def test_no_target_handler_raises(
        self, converter: ModalityConverter, text_input: ModalInput
    ) -> None:
        with pytest.raises(ValueError, match="No handler registered for target"):
            converter.convert(text_input, Modality.voice)

    def test_register_handler_adds_modality(
        self, converter: ModalityConverter
    ) -> None:
        assert Modality.voice not in converter.supported_modalities()
        # Register a minimal handler
        converter.register_handler(TextHandler())  # re-register text is fine
        assert Modality.text in converter.supported_modalities()

    def test_register_handler_replaces_existing(
        self, converter: ModalityConverter
    ) -> None:
        new_handler = TextHandler()
        converter.register_handler(new_handler)
        assert converter._handlers[Modality.text] is new_handler


# ---------------------------------------------------------------------------
# ModalityRouter tests
# ---------------------------------------------------------------------------


class TestModalityRouter:
    def test_route_text_input(
        self, router: ModalityRouter, text_input: ModalInput
    ) -> None:
        output = router.route(text_input)
        assert isinstance(output, ModalOutput)
        assert output.modality == Modality.text

    def test_route_structured_input(
        self, router: ModalityRouter, structured_input: ModalInput
    ) -> None:
        output = router.route(structured_input)
        assert output.modality == Modality.structured

    def test_route_unknown_modality_raises(
        self, router: ModalityRouter
    ) -> None:
        voice_input = ModalInput(modality=Modality.voice, content=b"audio")
        with pytest.raises(ValueError, match="No handler registered"):
            router.route(voice_input)

    def test_detect_json_object(self, router: ModalityRouter) -> None:
        raw = '{"key": "value"}'
        assert router.detect(raw) == Modality.structured

    def test_detect_json_array(self, router: ModalityRouter) -> None:
        raw = '[1, 2, 3]'
        assert router.detect(raw) == Modality.structured

    def test_detect_plain_text(self, router: ModalityRouter) -> None:
        raw = "This is just text, not JSON."
        assert router.detect(raw) == Modality.text

    def test_detect_invalid_json_like(self, router: ModalityRouter) -> None:
        raw = "{not valid json"
        assert router.detect(raw) == Modality.text

    def test_detect_bytes_json(self, router: ModalityRouter) -> None:
        raw = b'{"x": 1}'
        assert router.detect(raw) == Modality.structured

    def test_detect_bytes_text(self, router: ModalityRouter) -> None:
        raw = b"Hello world"
        assert router.detect(raw) == Modality.text

    def test_detect_empty_string(self, router: ModalityRouter) -> None:
        assert router.detect("") == Modality.text

    def test_detect_whitespace_only(self, router: ModalityRouter) -> None:
        assert router.detect("   ") == Modality.text


# ---------------------------------------------------------------------------
# _quality_score tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source, target, expected",
    [
        (Modality.text, Modality.structured, 0.95),
        (Modality.structured, Modality.text, 0.95),
        (Modality.text, Modality.text, 1.0),
        (Modality.structured, Modality.structured, 1.0),
        (Modality.text, Modality.voice, 0.5),
        (Modality.voice, Modality.text, 0.5),
        (Modality.image, Modality.video, 0.5),
    ],
)
def test_quality_score(
    source: Modality, target: Modality, expected: float
) -> None:
    assert _quality_score(source, target) == expected


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestModels:
    @pytest.mark.parametrize(
        "modality",
        [
            Modality.text,
            Modality.voice,
            Modality.image,
            Modality.video,
            Modality.structured,
        ],
    )
    def test_modality_enum_values(self, modality: Modality) -> None:
        assert isinstance(modality.value, str)

    def test_modal_input_default_metadata(self) -> None:
        inp = ModalInput(modality=Modality.text, content="hello")
        assert inp.metadata == {}

    def test_modal_input_default_mime_type(self) -> None:
        inp = ModalInput(modality=Modality.text, content="hello")
        assert inp.mime_type == "text/plain"

    def test_conversion_result_quality_bounds(self) -> None:
        output = ModalOutput(modality=Modality.text, content="x")
        with pytest.raises(Exception):
            ConversionResult(
                source_modality=Modality.text,
                target_modality=Modality.text,
                output=output,
                quality_score=1.5,  # above max
            )

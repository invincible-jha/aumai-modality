"""Shared test fixtures for aumai-modality."""

from __future__ import annotations

import json

import pytest

from aumai_modality.core import ModalityConverter, ModalityRouter, StructuredHandler, TextHandler
from aumai_modality.models import ModalInput, Modality


@pytest.fixture()
def text_handler() -> TextHandler:
    return TextHandler()


@pytest.fixture()
def structured_handler() -> StructuredHandler:
    return StructuredHandler()


@pytest.fixture()
def converter() -> ModalityConverter:
    return ModalityConverter()


@pytest.fixture()
def router() -> ModalityRouter:
    return ModalityRouter()


@pytest.fixture()
def text_input() -> ModalInput:
    return ModalInput(
        modality=Modality.text,
        content="Hello, this is plain text content.",
        mime_type="text/plain",
    )


@pytest.fixture()
def text_bytes_input() -> ModalInput:
    return ModalInput(
        modality=Modality.text,
        content=b"Binary encoded text content.",
        mime_type="text/plain",
    )


@pytest.fixture()
def structured_input() -> ModalInput:
    data = {"name": "Alice", "score": 42, "tags": ["ai", "agent"]}
    return ModalInput(
        modality=Modality.structured,
        content=json.dumps(data),
        mime_type="application/json",
    )


@pytest.fixture()
def structured_bytes_input() -> ModalInput:
    data = {"key": "value"}
    return ModalInput(
        modality=Modality.structured,
        content=json.dumps(data).encode("utf-8"),
        mime_type="application/json",
    )

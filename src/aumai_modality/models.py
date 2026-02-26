"""Pydantic models for aumai-modality."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "Modality",
    "ModalInput",
    "ModalOutput",
    "ConversionResult",
]


class Modality(str, Enum):
    """Supported interaction modalities."""

    text = "text"
    voice = "voice"
    image = "image"
    video = "video"
    structured = "structured"


class ModalInput(BaseModel):
    """An input payload in a specific modality."""

    modality: Modality
    content: bytes | str
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModalOutput(BaseModel):
    """An output payload in a specific modality."""

    modality: Modality
    content: bytes | str
    mime_type: str = "text/plain"


class ConversionResult(BaseModel):
    """Result of a modality conversion operation."""

    source_modality: Modality
    target_modality: Modality
    output: ModalOutput
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)

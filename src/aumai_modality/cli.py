"""CLI entry point for aumai-modality."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .core import ModalityConverter, ModalityRouter
from .models import ModalInput, Modality


@click.group()
@click.version_option()
def main() -> None:
    """AumAI Modality — multi-modal agent interaction framework."""


@main.command("convert")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Input file to convert.",
)
@click.option(
    "--target",
    "target_modality",
    required=True,
    type=click.Choice([m.value for m in Modality]),
    help="Target modality.",
)
@click.option(
    "--source-modality",
    "source_modality",
    default=None,
    type=click.Choice([m.value for m in Modality]),
    help="Source modality (auto-detected if omitted).",
)
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Write converted output to this file.",
)
def convert_command(
    input_path: str,
    target_modality: str,
    source_modality: str | None,
    output_path: str | None,
) -> None:
    """Convert a file from one modality to another."""
    raw_bytes = Path(input_path).read_bytes()

    router = ModalityRouter()
    if source_modality:
        detected = Modality(source_modality)
    else:
        detected = router.detect(raw_bytes)
        click.echo(f"Detected source modality: {detected.value}", err=True)

    modal_input = ModalInput(
        modality=detected,
        content=raw_bytes,
        mime_type=_guess_mime(input_path, detected),
    )

    converter = ModalityConverter()
    target = Modality(target_modality)

    try:
        result = converter.convert(modal_input, target)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    output_content = (
        result.output.content
        if isinstance(result.output.content, str)
        else result.output.content.decode("utf-8", errors="replace")
    )

    if output_path:
        Path(output_path).write_text(output_content, encoding="utf-8")
        click.echo(f"Converted output written to {output_path}")
    else:
        click.echo(output_content)

    click.echo(
        f"\nConversion: {result.source_modality.value} -> {result.target_modality.value}  "
        f"quality={result.quality_score:.2f}",
        err=True,
    )


@main.command("detect")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="File to detect modality for.",
)
def detect_command(input_path: str) -> None:
    """Detect the modality of a file."""
    raw_bytes = Path(input_path).read_bytes()
    router = ModalityRouter()
    detected = router.detect(raw_bytes)
    click.echo(f"Detected modality: {detected.value}")


def _guess_mime(path: str, modality: Modality) -> str:
    """Guess MIME type from file extension and modality."""
    ext = Path(path).suffix.lower()
    mime_map: dict[str, str] = {
        ".json": "application/json",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".mp4": "video/mp4",
    }
    return mime_map.get(ext, "application/octet-stream")


if __name__ == "__main__":
    main()

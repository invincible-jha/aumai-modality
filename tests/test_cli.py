"""Tests for aumai-modality CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from aumai_modality.cli import main, _guess_mime
from aumai_modality.models import Modality


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def text_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.txt"
    f.write_text("Hello, world! This is plain text.")
    return f


@pytest.fixture()
def json_file(tmp_path: Path) -> Path:
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"name": "Alice", "value": 99}))
    return f


@pytest.fixture()
def invalid_json_file(tmp_path: Path) -> Path:
    f = tmp_path / "broken.json"
    f.write_text("{not valid json}")
    return f


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


def test_cli_version(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


# ---------------------------------------------------------------------------
# detect command
# ---------------------------------------------------------------------------


def test_detect_text_file(runner: CliRunner, text_file: Path) -> None:
    result = runner.invoke(main, ["detect", "--input", str(text_file)])
    assert result.exit_code == 0
    assert "text" in result.output


def test_detect_json_file(runner: CliRunner, json_file: Path) -> None:
    result = runner.invoke(main, ["detect", "--input", str(json_file)])
    assert result.exit_code == 0
    assert "structured" in result.output


def test_detect_requires_input(runner: CliRunner) -> None:
    result = runner.invoke(main, ["detect"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# convert command
# ---------------------------------------------------------------------------


def test_convert_text_to_structured_stdout(
    runner: CliRunner, text_file: Path
) -> None:
    result = runner.invoke(
        main,
        ["convert", "--input", str(text_file), "--target", "structured"],
    )
    assert result.exit_code == 0
    # Output should contain JSON (the text wrapped in {text: ...})
    assert "{" in result.output


def test_convert_json_to_text_stdout(
    runner: CliRunner, json_file: Path
) -> None:
    result = runner.invoke(
        main,
        [
            "convert",
            "--input", str(json_file),
            "--target", "text",
            "--source-modality", "structured",
        ],
    )
    assert result.exit_code == 0
    assert "Alice" in result.output


def test_convert_text_to_text_same_modality(
    runner: CliRunner, text_file: Path
) -> None:
    result = runner.invoke(
        main,
        [
            "convert",
            "--input", str(text_file),
            "--target", "text",
            "--source-modality", "text",
        ],
    )
    assert result.exit_code == 0
    assert "Hello, world!" in result.output


def test_convert_auto_detects_source_modality(
    runner: CliRunner, json_file: Path
) -> None:
    result = runner.invoke(
        main,
        ["convert", "--input", str(json_file), "--target", "text"],
    )
    assert result.exit_code == 0
    # Detection message goes to stderr but CliRunner merges output
    assert "structured" in result.output or "Alice" in result.output


def test_convert_writes_output_file(
    runner: CliRunner, text_file: Path, tmp_path: Path
) -> None:
    out = tmp_path / "output.txt"
    result = runner.invoke(
        main,
        [
            "convert",
            "--input", str(text_file),
            "--target", "structured",
            "--output", str(out),
        ],
    )
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text()
    assert "{" in content
    assert "Converted output written to" in result.output


def test_convert_unknown_source_modality_exits_nonzero(
    runner: CliRunner, text_file: Path
) -> None:
    # voice modality has no handler — conversion should fail
    result = runner.invoke(
        main,
        [
            "convert",
            "--input", str(text_file),
            "--target", "voice",
            "--source-modality", "text",
        ],
    )
    assert result.exit_code == 1
    assert "Error" in result.output


def test_convert_requires_input(runner: CliRunner) -> None:
    result = runner.invoke(main, ["convert", "--target", "text"])
    assert result.exit_code != 0


def test_convert_requires_target(runner: CliRunner, text_file: Path) -> None:
    result = runner.invoke(main, ["convert", "--input", str(text_file)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# _guess_mime helper tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, modality, expected_mime",
    [
        ("file.json", Modality.structured, "application/json"),
        ("file.txt", Modality.text, "text/plain"),
        ("file.md", Modality.text, "text/markdown"),
        ("file.png", Modality.image, "image/png"),
        ("file.jpg", Modality.image, "image/jpeg"),
        ("file.jpeg", Modality.image, "image/jpeg"),
        ("file.mp3", Modality.voice, "audio/mpeg"),
        ("file.wav", Modality.voice, "audio/wav"),
        ("file.mp4", Modality.video, "video/mp4"),
        ("file.bin", Modality.image, "application/octet-stream"),
    ],
)
def test_guess_mime(
    path: str, modality: Modality, expected_mime: str
) -> None:
    assert _guess_mime(path, modality) == expected_mime


# ---------------------------------------------------------------------------
# help text
# ---------------------------------------------------------------------------


def test_help_text(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "convert" in result.output
    assert "detect" in result.output


def test_convert_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["convert", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.output
    assert "--target" in result.output

"""Utility functions for exporting data to various formats."""

from pathlib import Path


def get_output_path(base_path: Path, schema: str, extension: str | None = None) -> Path:
    """Get the output path for a file export with the proper extension."""
    stem = base_path.stem
    parent = base_path.parent

    filename = f"{stem}_{schema}"

    ext = extension or base_path.suffix
    if ext and not ext.startswith("."):
        ext = f".{ext}"

    return parent / f"{filename}{ext}"

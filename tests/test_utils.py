"""Utility functions for testing."""

import logging
import re
from pathlib import Path
from typing import Optional


def find_timestamped_file(
    directory: Path, base_name: str, file_extension: str
) -> Optional[Path]:
    """Find a file with a timestamp in the name.

    Args:
        directory: Directory to search in
        base_name: Base name of the file (before the timestamp)
        file_extension: File extension (without the dot)

    Returns:
        Path to the file if found, None otherwise
    """
    # Create the pattern to match files with timestamps
    # Format is typically: base_name_schema_YYYYMMDD_HHMMSS.extension
    pattern = f"{base_name}_[a-z]+_\\d{{8}}_\\d{{6}}\\.{file_extension}"

    logging.debug(f"Looking for files matching pattern: {pattern}")

    # Find all files matching the pattern
    matching_files = list(directory.glob(f"{base_name}_*_{file_extension}"))
    regex = re.compile(pattern)
    matches = [f for f in matching_files if regex.match(f.name)]

    # Sort by modification time (newest first) as a reasonable fallback
    matches.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    if not matches:
        logging.warning(f"No files found matching pattern {pattern} in {directory}")
        return None

    logging.debug(f"Found matching files: {matches}")
    return matches[0]


def find_schema_file(
    directory: Path, base_name: str, schema_name: str, file_extension: str
) -> Optional[Path]:
    """Find a specific schema file with a timestamp in the name.

    Args:
        directory: Directory to search in
        base_name: Base name of the file (before the schema name)
        schema_name: Name of the schema (e.g., 'acc', 'gyro')
        file_extension: File extension (without the dot)

    Returns:
        Path to the file if found, None otherwise
    """
    # Create the pattern for this specific schema
    pattern = f"{base_name}_{schema_name}_\\d{{8}}_\\d{{6}}\\.{file_extension}"

    logging.debug(f"Looking for files matching pattern: {pattern}")

    # Find all files matching the pattern
    regex = re.compile(pattern)
    matches = [f for f in directory.glob(f"{base_name}_*") if regex.match(f.name)]

    # Sort by modification time (newest first) as a reasonable fallback
    matches.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    if not matches:
        logging.warning(
            f"No {schema_name} files found matching pattern {pattern} in {directory}"
        )
        return None

    logging.debug(f"Found matching {schema_name} files: {matches}")
    return matches[0]

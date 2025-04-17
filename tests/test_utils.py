"""Utility functions for testing."""

import logging
import re
from pathlib import Path


# Get the directory where this file is located and resolve paths
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent
TESTFILES_DIR = TEST_DIR / "testfiles"
if not TESTFILES_DIR.exists():
    # If testfiles is in the project root instead of tests directory
    TESTFILES_DIR = PROJECT_ROOT / "testfiles"


def get_test_file_path(filename: str) -> Path:
    """Get the absolute path to a test file."""
    file_path = TESTFILES_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Test file not found: {file_path}")
    return file_path


def find_timestamped_file(directory: Path, base_name: str, file_extension: str) -> Path | None:
    """Find a file with a timestamp in the name."""
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


def find_schema_file(directory: Path, base_name: str, schema_name: str, file_extension: str) -> Path | None:
    """Find a specific schema file with a timestamp in the name."""
    # Create the pattern for this specific schema
    pattern = f"{base_name}_{schema_name}_\\d{{8}}_\\d{{6}}\\.{file_extension}"

    logging.debug(f"Looking for files matching pattern: {pattern}")

    # Find all files matching the pattern
    regex = re.compile(pattern)
    matches = [f for f in directory.glob(f"{base_name}_*") if regex.match(f.name)]

    # Sort by modification time (newest first) as a reasonable fallback
    matches.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    if not matches:
        logging.warning(f"No {schema_name} files found matching pattern {pattern} in {directory}")
        return None

    logging.debug(f"Found matching {schema_name} files: {matches}")
    return matches[0]

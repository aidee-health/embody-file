"""Common utilities for exporters to reduce code duplication."""

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from ..models import Data
from ..schemas import ExportSchema, DataType


def ensure_directory(file_path: Path) -> None:
    """Ensure parent directory exists for file_path."""
    file_path.parent.mkdir(parents=True, exist_ok=True)


def export_device_info_to_dataframe(data: Data) -> pd.DataFrame | None:
    """Convert device info to DataFrame if available."""
    if hasattr(data, "device_info") and data.device_info:
        info = {k: [v] for k, v in asdict(data.device_info).items()}
        return pd.DataFrame(info)
    return None


def should_skip_schema(schema: ExportSchema, schema_filter: set[DataType] | None) -> bool:
    """Check if schema should be skipped based on filter."""
    return bool(schema_filter and schema.data_type not in schema_filter)


def log_export_start(format_name: str, output_path: Path) -> None:
    """Log the start of an export operation."""
    logging.info(f"Exporting data to {format_name} format: {output_path}")


def prepare_timestamp_column(df: pd.DataFrame, timezone: Any = None) -> pd.DataFrame:
    """Prepare timestamp column as datetime index, creating a copy.

    Converts timestamp to datetime, sets as index, and sorts.
    """
    # Create a copy to avoid modifying the original
    df = df.copy()

    if "timestamp" in df.columns:
        # Convert to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        # Set as index
        df = df.set_index("timestamp")

        # Localize timezone if provided
        if timezone and not df.index.tz:
            df.index = df.index.tz_localize(timezone)

        # Sort by index
        df = df.sort_index()
    elif isinstance(df.index, pd.DatetimeIndex):
        # Already has datetime index, just sort
        df = df.sort_index()

    return df


def store_hdf_frequency_metadata(store: pd.HDFStore, schema_name: str, data: Data) -> None:
    """Store sampling frequency as HDF metadata attributes."""
    from ..schemas import SchemaRegistry, DataType

    if schema_name == SchemaRegistry.SCHEMAS[DataType.ECG_PPG].name and data.ecg_ppg_sample_frequency:
        # Store the sampling frequency as metadata that clients can read
        storer = store.get_storer(schema_name)
        if storer:
            storer.attrs.sample_frequency_hz = data.ecg_ppg_sample_frequency
            storer.attrs.sample_period_ms = 1000.0 / data.ecg_ppg_sample_frequency

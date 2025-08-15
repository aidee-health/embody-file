"""Common utilities for exporters to reduce code duplication."""

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from ..models import Data
from ..schemas import ExportSchema, DataType


def ensure_directory(file_path: Path) -> None:
    """Ensure the parent directory of a file path exists.

    Args:
        file_path: Path to file whose parent directory should exist
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)


def export_device_info_to_dataframe(data: Data) -> pd.DataFrame | None:
    """Convert device info to a DataFrame if available.

    Args:
        data: Data object potentially containing device_info

    Returns:
        DataFrame with device info or None if not available
    """
    if hasattr(data, "device_info") and data.device_info:
        info = {k: [v] for k, v in asdict(data.device_info).items()}
        return pd.DataFrame(info)
    return None


def should_skip_schema(schema: ExportSchema, schema_filter: set[DataType] | None) -> bool:
    """Check if a schema should be skipped based on filter.

    Args:
        schema: Export schema to check
        schema_filter: Optional set of DataTypes to include

    Returns:
        True if schema should be skipped, False otherwise
    """
    return bool(schema_filter and schema.data_type not in schema_filter)


def log_export_start(format_name: str, output_path: Path) -> None:
    """Log the start of an export operation.

    Args:
        format_name: Name of the export format (e.g., "CSV", "HDF", "Parquet")
        output_path: Path where data will be exported
    """
    logging.info(f"Exporting data to {format_name} format: {output_path}")


def prepare_timestamp_column(df: pd.DataFrame, timezone: Any = None) -> pd.DataFrame:
    """Prepare timestamp column/index for export.

    Handles conversion to datetime and setting as index if needed.
    Creates a copy to avoid modifying the original DataFrame.

    Args:
        df: DataFrame to process
        timezone: Optional timezone for localization (e.g., pytz.utc)

    Returns:
        Processed DataFrame with timestamp handling
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
    """Store frequency metadata for HDF files.

    Args:
        store: Open HDFStore object
        schema_name: Name of the schema/key in the store
        data: Data object containing frequency information
    """
    from ..schemas import SchemaRegistry, DataType

    if schema_name == SchemaRegistry.SCHEMAS[DataType.ECG_PPG].name and data.ecg_ppg_sample_frequency:
        # Store the sampling frequency as metadata that clients can read
        storer = store.get_storer(schema_name)
        if storer:
            storer.attrs.sample_frequency_hz = data.ecg_ppg_sample_frequency
            storer.attrs.sample_period_ms = 1000.0 / data.ecg_ppg_sample_frequency

"""Data formatters for standardized export."""

from dataclasses import astuple
from dataclasses import fields
from typing import Any

import pandas as pd

from .models import Data
from .schemas import DataType
from .schemas import ExportSchema


class DataFormatter:
    """Formats data according to export schemas."""

    def format_data(self, data: Data, schema: ExportSchema) -> pd.DataFrame:
        """Format data according to the provided schema."""
        # Handle ECG_PPG data type specially due to the multi-channel format
        if schema.data_type == DataType.ECG_PPG:
            df = self._format_ecg_ppg_data(data, schema)
        else:
            # Use standard formatting for other data types
            df = self._format_standard_data(data, schema)

        # Ensure all schema columns exist with proper types
        df = self._apply_schema_to_dataframe(df, schema)

        return df

    def _format_ecg_ppg_data(self, data: Data, schema: ExportSchema) -> pd.DataFrame:
        """Special formatter for physiological data (ECG/PPG)."""
        # First try multi-channel data
        if hasattr(data, "multi_ecg_ppg_data") and data.multi_ecg_ppg_data:
            # Process multi-channel data
            df = self._to_dataframe(data.multi_ecg_ppg_data, is_multi_channel=True)

            if not df.empty:
                return df

        # Fall back to sensor data (single PPG channel)
        if hasattr(data, "sensor") and data.sensor:
            df = self._to_dataframe(data.sensor)

            if not df.empty:
                return df

        # No data found
        return pd.DataFrame(columns=schema.columns)

    def _format_standard_data(self, data: Data, schema: ExportSchema) -> pd.DataFrame:
        """Standard formatter for regular data types."""
        # Try each source attribute in order
        for attr_name in schema.source_attributes:
            if hasattr(data, attr_name) and getattr(data, attr_name):
                df = self._to_dataframe(getattr(data, attr_name))
                if not df.empty:
                    return df

        # No data found
        return pd.DataFrame(columns=schema.columns)

    def _to_dataframe(self, data_list: list[tuple[int, Any]], is_multi_channel: bool = False) -> pd.DataFrame:
        """Convert data to a pandas DataFrame.

        This unified method handles both standard and multi-channel data.

        Args:
            data_list: List of (timestamp, data) tuples
            is_multi_channel: Whether this is multi-channel (ECG/PPG) data

        Returns:
            DataFrame with the data
        """
        if not data_list:
            return pd.DataFrame()

        if is_multi_channel:
            # Handle multi-channel data (ECG/PPG)
            first_item = data_list[0][1]
            num_ecg = getattr(first_item, "no_of_ecgs", 0)
            num_ppg = getattr(first_item, "no_of_ppgs", 0)

            columns = ["timestamp"] + [f"ecg_{i}" for i in range(num_ecg)] + [f"ppg_{i}" for i in range(num_ppg)]

            column_data = []
            for ts, d in data_list:
                ecgs = getattr(d, "ecgs", [])[:num_ecg]
                ppgs = getattr(d, "ppgs", [])[:num_ppg]
                column_data.append((ts, *tuple(ecgs), *tuple(ppgs)))
        else:
            # Handle standard data
            try:
                columns = ["timestamp"] + [f.name for f in fields(data_list[0][1])]
                column_data = [(ts, *astuple(d)) for ts, d in data_list]
            except (AttributeError, TypeError):
                # Fallback for non-dataclass objects or plain tuples
                if isinstance(data_list[0][1], dict):
                    # Handle dictionary data
                    columns = ["timestamp", *list(data_list[0][1].keys())]
                    column_data = [(ts, *d.values()) for ts, d in data_list]
                else:
                    # Cannot determine structure, return empty DataFrame
                    return pd.DataFrame()

        df = pd.DataFrame(column_data, columns=columns)

        return df

    def _apply_schema_to_dataframe(self, df: pd.DataFrame, schema: ExportSchema) -> pd.DataFrame:
        """Apply schema column mapping to a DataFrame."""
        if df.empty:
            return pd.DataFrame(columns=schema.columns)

        # Apply column mapping
        if hasattr(schema, "column_mapping") and schema.column_mapping:
            for src_col, dst_col in schema.column_mapping.items():
                if src_col in df.columns:
                    df[dst_col] = df[src_col]

        # Ensure all required columns exist
        for col in schema.columns:
            if col not in df.columns:
                df[col] = None

        # Return only the columns defined in the schema, in the correct order
        result_df = pd.DataFrame(columns=schema.columns)
        for col in schema.columns:
            if col in df.columns:
                result_df[col] = df[col]

        return result_df

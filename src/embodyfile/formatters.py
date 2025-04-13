"""Data formatters for standardized export."""

import logging
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
        """Format data according to the provided schema.

        Args:
            data: The data to format
            schema: The schema to apply

        Returns:
            DataFrame formatted according to the schema
        """
        # Handle PHYSIO data type specially due to the multi-channel format
        if schema.data_type == DataType.PHYSIO:
            df = self._format_physio_data(data, schema)
        else:
            # Use standard formatting for other data types
            df = self._format_standard_data(data, schema)

        # Ensure all schema columns exist with proper types
        df = self._apply_schema_to_dataframe(df, schema)

        return df

    def _format_physio_data(self, data: Data, schema: ExportSchema) -> pd.DataFrame:
        """Special formatter for physiological data (ECG/PPG).

        Args:
            data: The data to format
            schema: The schema to apply

        Returns:
            DataFrame with physiological data
        """
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
        """Standard formatter for regular data types.

        Args:
            data: The data to format
            schema: The schema to apply

        Returns:
            DataFrame with formatted data
        """
        # Try each source attribute in order
        for attr_name in schema.source_attributes:
            if hasattr(data, attr_name) and getattr(data, attr_name):
                df = self._to_dataframe(getattr(data, attr_name))
                if not df.empty:
                    return df

        # No data found
        return pd.DataFrame(columns=schema.columns)

    def _to_dataframe(
        self, data_list: list[tuple[int, Any]], is_multi_channel: bool = False
    ) -> pd.DataFrame:
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

            columns = (
                ["timestamp"]
                + [f"ecg_{i}" for i in range(num_ecg)]
                + [f"ppg_{i}" for i in range(num_ppg)]
            )

            column_data = []
            for ts, d in data_list:
                ecgs = getattr(d, "ecgs", [])[:num_ecg]
                ppgs = getattr(d, "ppgs", [])[:num_ppg]
                column_data.append((ts,) + tuple(ecgs) + tuple(ppgs))
        else:
            # Handle standard data
            try:
                columns = ["timestamp"] + [f.name for f in fields(data_list[0][1])]
                column_data = [(ts, *astuple(d)) for ts, d in data_list]
            except (AttributeError, TypeError):
                # Fallback for non-dataclass objects or plain tuples
                if isinstance(data_list[0][1], dict):
                    # Handle dictionary data
                    columns = ["timestamp"] + list(data_list[0][1].keys())
                    column_data = [(ts, *d.values()) for ts, d in data_list]
                else:
                    # Cannot determine structure, return empty DataFrame
                    return pd.DataFrame()

        # Create DataFrame
        df = pd.DataFrame(column_data, columns=columns)

        # Make sure timestamp is available as regular column
        if "timestamp" not in df.columns:
            return pd.DataFrame()

        # Ensure timestamp is treated as a regular column, not as an index
        # This avoids the DatetimeIndex error
        df = df.copy()

        return df

    def _apply_schema_to_dataframe(
        self, df: pd.DataFrame, schema: ExportSchema
    ) -> pd.DataFrame:
        """Apply schema column mapping and data types to a DataFrame.

        Args:
            df: The DataFrame to process
            schema: The schema to apply

        Returns:
            Processed DataFrame conforming to schema
        """
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

        # Apply data types
        for col, dtype in schema.dtypes.items():
            if col in df.columns and not df[col].isna().all():
                try:
                    # First fill NaN/None values with appropriate defaults based on dtype
                    if "int" in dtype:
                        df[col] = df[col].fillna(0)
                    elif "float" in dtype:
                        df[col] = df[col].fillna(0.0)
                    elif "bool" in dtype:
                        df[col] = df[col].fillna(False)

                    # Now convert to the specified dtype
                    df[col] = df[col].astype(dtype)
                except Exception as e:
                    logging.warning(f"Could not convert column {col} to {dtype}: {e}")

        # Return only the columns defined in the schema, in the correct order
        result_df = pd.DataFrame(columns=schema.columns)
        for col in schema.columns:
            if col in df.columns:
                result_df[col] = df[col]

        return result_df


class HDFCompatibilityFormatter(DataFormatter):
    """Formatter with special handling for HDF compatibility."""

    def format_imu_data(self, data: Data) -> pd.DataFrame:
        """Special formatter for combined IMU data (accelerometer + gyroscope).

        This maintains compatibility with the original HDF format where
        accelerometer and gyroscope are merged into a single "imu" dataset.

        Args:
            data: The data to format

        Returns:
            DataFrame with combined IMU data
        """
        if (
            not hasattr(data, "acc")
            or not data.acc
            or not hasattr(data, "gyro")
            or not data.gyro
        ):
            return pd.DataFrame()

        # Format accelerometer and gyroscope data
        acc_df = self._to_dataframe(data.acc)
        gyro_df = self._to_dataframe(data.gyro)

        if acc_df.empty or gyro_df.empty:
            return pd.DataFrame()

        # Simply combine columns since we're not using indexing now
        if "timestamp" in acc_df.columns and "timestamp" in gyro_df.columns:
            # Use a simple join on timestamp column
            df_imu = pd.merge(
                acc_df, gyro_df, on="timestamp", how="inner", suffixes=("", "_gyro")
            )

            # Remove duplicate timestamp columns if any
            if "timestamp_gyro" in df_imu.columns:
                df_imu = df_imu.drop(columns=["timestamp_gyro"])

            return df_imu

        return pd.DataFrame()

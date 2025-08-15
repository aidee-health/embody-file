"""HDF exporter implementation."""

import logging
from pathlib import Path

import pandas as pd
from typing import Literal

from ..models import Data
from ..schemas import SchemaRegistry
from . import BaseExporter
from .common import (
    ensure_directory,
    export_device_info_to_dataframe,
    log_export_start,
    prepare_timestamp_column,
    should_skip_schema,
    store_hdf_frequency_metadata,
)


class HDFExporter(BaseExporter):
    """HDF exporter that writes all data to a single file with multiple groups."""

    # Define file extension for HDF files
    FILE_EXTENSION = "hdf5"

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to HDF file."""
        log_export_start("HDF", output_path)

        # Add extension if not present
        if output_path.suffix.lower() != f".{self.FILE_EXTENSION}":
            output_path = output_path.with_suffix(f".{self.FILE_EXTENSION}")

        # Create parent directory if it doesn't exist
        ensure_directory(output_path)

        # Write mode for first schema, append mode for subsequent schemas
        mode: Literal["a", "w", "r+"] = "w"

        # Export each schema to the same file with different keys
        exported_schemas = []
        for schema in SchemaRegistry.get_schemas_for_export():
            # Skip schemas that don't match our filter
            if should_skip_schema(schema, self._schema_filter):
                continue

            # Format data according to schema
            df = self.formatter.format_data(data, schema)

            if df.empty:
                logging.debug(f"No data to export for schema {schema.name}")
                continue

            # Export the formatted data to the HDF file
            self._export_dataframe_to_hdf(data, df, output_path, schema.name, mode)

            # Use append mode for subsequent schemas
            mode = "a"

            exported_schemas.append(schema.name)

        # Export device info as well
        device_info = export_device_info_to_dataframe(data)
        if device_info is not None:
            device_info.to_hdf(output_path, key="device_info", mode="a", complevel=4)
            exported_schemas.append("device_info")

        if exported_schemas:
            logging.info(f"Exported schemas {', '.join(exported_schemas)} to HDF file: {output_path}")
        else:
            logging.warning(f"No data exported to HDF file: {output_path}")

    def _export_dataframe(self, data: Data, df: pd.DataFrame, file_path: Path, schema_name: str) -> None:
        """Export dataframe to HDF."""
        self._export_dataframe_to_hdf(data, df, file_path, schema_name, "w")

    def _export_dataframe_to_hdf(
        self, data: Data, df: pd.DataFrame, file_path: Path, schema_name: str, mode: Literal["a", "w", "r+"] = "a"
    ) -> None:
        """Export dataframe to HDF with specified mode."""
        ensure_directory(file_path)

        # Prepare timestamp column/index
        df = prepare_timestamp_column(df)

        # Store dataframe with frequency as metadata attribute instead of setting index.freq
        with pd.HDFStore(file_path, mode=mode) as store:
            store.put(schema_name, df, format="table", complevel=4, complib="zlib")
            store_hdf_frequency_metadata(store, schema_name, data)

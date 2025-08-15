"""CSV exporter implementation."""

import logging
from pathlib import Path

import pandas as pd

from ..models import Data
from ..schemas import SchemaRegistry
from ..export_utils import get_output_path
from . import BaseExporter
from .common import (
    ensure_directory,
    export_device_info_to_dataframe,
    log_export_start,
    should_skip_schema,
)


class CSVExporter(BaseExporter):
    """CSV exporter that creates separate files per data type."""

    # Define file extension for CSV files
    FILE_EXTENSION = "csv"

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to CSV files."""
        log_export_start("CSV", output_path)

        # Export each schema
        exported_files = []
        for schema in SchemaRegistry.get_schemas_for_export():
            # Skip schemas that don't match our filter
            if should_skip_schema(schema, self._schema_filter):
                continue

            result = self.export_by_schema(data, output_path, schema)
            if result:
                exported_files.append(result)

        # Export device info as well
        device_info = export_device_info_to_dataframe(data)
        if device_info is not None:
            device_info_file = get_output_path(output_path, "device_info", self.FILE_EXTENSION)
            self._export_dataframe(data, device_info, device_info_file, "device_info")
            logging.info(f"Exported device info to CSV format: {device_info_file}")

        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Exported {len(exported_files)} files to CSV format")

    def _export_dataframe(self, data: Data, df: pd.DataFrame, file_path: Path, schema_name: str) -> None:
        """Export dataframe to CSV."""
        # Create parent directory if it doesn't exist
        ensure_directory(file_path)

        # Export to CSV with proper data types
        df.to_csv(file_path, index=False)

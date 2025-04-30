"""Parquet exporter implementation."""

import logging
from pathlib import Path

import pandas as pd

from ..models import Data
from ..schemas import SchemaRegistry
from ..export_utils import get_output_path
from . import BaseExporter


class ParquetExporter(BaseExporter):
    """Exporter for Parquet format."""

    # Define file extension for Parquet files
    FILE_EXTENSION = "parquet"

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to Parquet format."""
        logging.info(f"Exporting data to Parquet format: {output_path}")

        # Export each schema
        exported_files = []
        for schema in SchemaRegistry.get_schemas_for_export():
            # Skip schemas that don't match our filter
            if self._schema_filter and schema.data_type not in self._schema_filter:
                continue

            result = self.export_by_schema(data, output_path, schema)
            if result:
                exported_files.append(result)

        # Export device info as well
        if hasattr(data, "device_info") and data.device_info:
            from dataclasses import asdict

            info = {k: [v] for k, v in asdict(data.device_info).items()}
            device_info = pd.DataFrame(info)
            device_info_file = get_output_path(output_path, "deviceinfo", self.FILE_EXTENSION)
            self._export_dataframe(device_info, device_info_file, "deviceinfo")

        logging.info(f"Exported {len(exported_files)} files to Parquet format")

    def _export_dataframe(self, df: pd.DataFrame, file_path: Path, schema_name: str) -> None:
        """Export a dataframe to Parquet."""
        # Create parent directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Export to Parquet format
        df.to_parquet(file_path, engine="pyarrow", index=False, compression="snappy")

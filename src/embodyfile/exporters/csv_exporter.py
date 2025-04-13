"""CSV exporter implementation."""

import logging
from pathlib import Path

import pandas as pd

from ..models import Data
from ..schemas import ExportSchema
from ..schemas import SchemaRegistry
from . import BaseExporter


class CSVExporter(BaseExporter):
    """Exporter for CSV format."""

    # Define file extension for CSV files
    FILE_EXTENSION = "csv"

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to CSV format.

        Args:
            data: The data to export
            output_path: Base path where the CSV files should be saved
        """
        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Exporting data to CSV format: {output_path}")

        # Export each schema
        exported_files = []
        for schema in SchemaRegistry.get_schemas_for_export():
            # Skip schemas that don't match our filter
            if self._schema_filter and schema.data_type not in self._schema_filter:
                continue

            result = self.export_by_schema(data, output_path, schema)
            if result:
                exported_files.append(result)

        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Exported {len(exported_files)} files to CSV format")

    def _export_dataframe(
        self, df: pd.DataFrame, file_path: Path, schema: ExportSchema
    ) -> None:
        """Export a dataframe to CSV.

        Args:
            df: The dataframe to export
            file_path: Path where the CSV should be saved
            schema: The schema used for the export
        """
        # Create parent directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Export to CSV with proper data types
        df.to_csv(file_path, index=False)

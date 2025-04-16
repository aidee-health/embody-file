"""Base class for exporters."""

import logging
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Optional

import pandas as pd

from ..formatters import DataFormatter
from ..models import Data
from ..schemas import DataType
from ..schemas import ExportSchema


class BaseExporter(ABC):
    """Base class for data exporters."""

    # The file extension this exporter produces (to be overridden by subclasses)
    FILE_EXTENSION = ""

    def __init__(self):
        """Initialize the exporter."""
        self.formatter = DataFormatter()
        self._schema_filter: Optional[set[DataType]] = None

    def set_schema_filter(self, data_types: list[DataType]) -> None:
        """Set a filter to only export specific data types.

        Args:
            data_types: List of data types to export
        """
        self._schema_filter = set(data_types)

    @abstractmethod
    def export(self, data: Data, output_path: Path) -> None:
        """Export data to a specific format."""
        pass

    def export_by_schema(
        self, data: Data, output_path: Path, schema: ExportSchema
    ) -> Optional[Path]:
        """Export data according to a specific schema."""
        try:
            # Format data according to schema
            df = self.formatter.format_data(data, schema)

            if df.empty:
                logging.debug(f"No data to export for schema {schema.name}")
                return None

            # Get output path for this specific schema with the proper extension
            file_path = self._get_schema_output_path(output_path, schema, data)

            # Export the formatted data
            self._export_dataframe(df, file_path, schema)

            logging.info(f"Exported {schema.name} data to {file_path}")
            return file_path

        except Exception as e:
            logging.error(f"Error exporting {schema.name} data: {str(e)}")
            return None

    @abstractmethod
    def _export_dataframe(
        self, df: pd.DataFrame, file_path: Path, schema: ExportSchema
    ) -> None:
        """Export a dataframe to the specified path using the given schema. Override in each subclass."""
        pass

    def _get_schema_output_path(
        self, base_path: Path, schema: ExportSchema, data: Data
    ) -> Path:
        """Get the output path for a specific schema with the correct file extension."""
        # Try to get a timestamp
        timestamp: Optional[Any] = None

        # From device info
        if hasattr(data, "device_info") and data.device_info:
            if hasattr(data.device_info, "timestamp") and data.device_info.timestamp:
                timestamp = data.device_info.timestamp

        # From filename
        if not timestamp:
            timestamp = self._extract_timestamp_from_path(base_path)

        # Get the path with the correct extension for this exporter
        return schema.get_output_path(
            base_path, timestamp, extension=self.FILE_EXTENSION
        )

    def _extract_timestamp_from_path(self, path: Path) -> Optional[datetime]:
        """Try to extract a timestamp from the path name."""
        try:
            import re

            stem = path.stem

            # Try to find a pattern like YYYYMMDD_HHMMSS
            match = re.search(r"(\d{8}_\d{6})", stem)
            if match:
                timestamp_str = match.group(1)
                return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

            return None

        except Exception:
            return None

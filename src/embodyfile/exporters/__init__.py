"""Base class for exporters."""

import logging
from abc import ABC
from abc import abstractmethod
from pathlib import Path

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
        self.formatter = DataFormatter()
        self._schema_filter: set[DataType] | None = None

    def set_schema_filter(self, data_types: list[DataType]) -> None:
        """Set a filter to only export specific data types."""
        self._schema_filter = set(data_types)

    @abstractmethod
    def export(self, data: Data, output_path: Path) -> None:
        """Export data to a specific format."""
        pass

    def export_by_schema(self, data: Data, output_path: Path, schema: ExportSchema) -> Path | None:
        """Export data according to a specific schema."""
        try:
            df = self.formatter.format_data(data, schema)

            if df.empty:
                logging.debug(f"No data to export for schema {schema.name}")
                return None

            file_path = self._get_schema_output_path(output_path, schema)
            self._export_dataframe(df, file_path, schema)

            logging.info(f"Exported {schema.name} data to {file_path}")
            return file_path

        except Exception as e:
            logging.error(f"Error exporting {schema.name} data: {e!s}", exc_info=True)
            return None

    @abstractmethod
    def _export_dataframe(self, df: pd.DataFrame, file_path: Path, schema_name: str) -> None:
        """Export a dataframe to the specified path using the given schema. Override in each subclass."""
        pass

    def _get_schema_output_path(self, base_path: Path, schema: ExportSchema) -> Path:
        """Get the output path for a specific schema with the correct file extension."""
        return schema.get_output_path(base_path, self.FILE_EXTENSION)

"""HDF exporter implementation."""

import logging
from pathlib import Path

import pandas as pd

from ..models import Data
from ..schemas import ExportSchema
from ..schemas import SchemaRegistry
from . import BaseExporter


class HDFExporter(BaseExporter):
    """Exporter for HDF format with all schemas in the same file."""

    # Define file extension for HDF files
    FILE_EXTENSION = "hdf"

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to a single HDF file with multiple datasets.

        Args:
            data: The data to export
            output_path: Path where the HDF file should be saved
        """
        logging.info(f"Exporting data to HDF: {output_path}")

        # Add extension if not present
        if output_path.suffix.lower() != f".{self.FILE_EXTENSION}":
            output_path = output_path.with_suffix(f".{self.FILE_EXTENSION}")

        # Create parent directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use all available schemas
        schemas = SchemaRegistry.get_schemas_for_export()

        # Export each schema as a separate dataset in the same HDF file
        for schema in schemas:
            try:
                # Format data according to schema
                df = self.formatter.format_data(data, schema)

                if df.empty:
                    logging.debug(f"No data to export for schema {schema.name}")
                    continue

                # Export to HDF with schema name as the dataset key
                self._export_dataset(df, output_path, schema)

                logging.debug(f"Exported {schema.name} dataset to {output_path}")
            except Exception as e:
                logging.error(f"Error exporting {schema.name} dataset: {str(e)}")

        logging.info(f"Exported all data to HDF file: {output_path}")

    def _export_dataset(
        self, df: pd.DataFrame, file_path: Path, schema: ExportSchema
    ) -> None:
        """Export a dataframe as a dataset within an HDF file.

        Args:
            df: The dataframe to export
            file_path: Path where the HDF file should be saved
            schema: The schema used for the export
        """
        # Determine HDF key from schema
        hdf_key = schema.name

        # Determine mode (first dataset uses 'w', rest use 'a')
        mode = "a" if file_path.exists() else "w"

        # Make a copy of the dataframe to avoid modifying the original
        df_export = df.copy()

        # Handle NaN values based on column types
        for col, dtype in schema.dtypes.items():
            if col in df_export.columns:
                if df_export[col].isna().any():
                    # First convert to the desired dtype where possible
                    # This will handle non-null values
                    non_null_mask = ~df_export[col].isna()

                    if non_null_mask.any():
                        # Convert non-null values first
                        try:
                            # For non-null values, convert to the target type first
                            df_export.loc[non_null_mask, col] = df_export.loc[
                                non_null_mask, col
                            ].astype(dtype)
                        except Exception as e:
                            logging.warning(
                                f"Could not convert non-null values in {col} to {dtype}: {e}"
                            )

                    # Now fill null values with type-appropriate defaults
                    if "int" in dtype:
                        df_export.loc[~non_null_mask, col] = 0
                    elif "float" in dtype:
                        df_export.loc[~non_null_mask, col] = 0.0
                    elif "bool" in dtype:
                        df_export.loc[~non_null_mask, col] = False
                    else:
                        df_export.loc[~non_null_mask, col] = ""

                    # Ensure the entire column has the correct dtype
                    try:
                        df_export[col] = df_export[col].astype(dtype)
                    except Exception as e:
                        logging.warning(
                            f"Could not convert column {col} to {dtype}: {e}"
                        )
                else:
                    # If no NaN values, just convert directly
                    try:
                        df_export[col] = df_export[col].astype(dtype)
                    except Exception as e:
                        logging.warning(
                            f"Could not convert column {col} to {dtype}: {e}"
                        )

        # Export to HDF format
        df_export.to_hdf(file_path, key=hdf_key, mode=mode)

    def _export_dataframe(
        self, df: pd.DataFrame, file_path: Path, schema: ExportSchema
    ) -> None:
        """Export a dataframe to HDF.

        This method is called from BaseExporter.export_by_schema and needs to be implemented,
        but for HDF we're overriding the export method to handle all schemas at once.
        In case this method is called directly, we'll still handle it correctly.

        Args:
            df: The dataframe to export
            file_path: Path where the HDF file should be saved
            schema: The schema used for the export
        """
        # Add extension if not present
        if file_path.suffix.lower() != f".{self.FILE_EXTENSION}":
            file_path = file_path.with_suffix(f".{self.FILE_EXTENSION}")

        # Export dataset
        self._export_dataset(df, file_path, schema)

    def _get_schema_output_path(
        self, base_path: Path, schema: ExportSchema, data: Data
    ) -> Path:
        """Override to ensure all schemas go to the same file for HDF.

        Args:
            base_path: Base output path
            schema: Schema being exported
            data: The data being exported

        Returns:
            Path for the HDF file (same for all schemas)
        """
        # For HDF, we always use the base_path with .h5 extension
        if base_path.suffix.lower() != f".{self.FILE_EXTENSION}":
            return base_path.with_suffix(f".{self.FILE_EXTENSION}")
        return base_path

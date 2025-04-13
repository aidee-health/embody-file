"""HDF exporter implementation."""

import logging
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from ..formatters import HDFCompatibilityFormatter
from ..models import Data
from ..schemas import DataType
from ..schemas import ExportSchema
from ..schemas import SchemaRegistry
from . import BaseExporter


class HDFExporter(BaseExporter):
    """Exporter for HDF format with backward compatibility."""

    def __init__(self):
        """Initialize the HDF exporter with specialized formatter."""
        super().__init__()
        # Override the formatter with the HDF compatibility formatter
        self.formatter = HDFCompatibilityFormatter()

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to HDF format maintaining backward compatibility.

        Args:
            data: The data to export
            output_path: Path where the HDF file should be saved
        """
        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Converting data to HDF: {output_path}")

        # Create the output directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Format and export legacy sensor data
        df_data = self.formatter.format_data(data, SchemaRegistry.SENSOR_DATA)
        if not df_data.empty:
            # Filter out values that are too large
            df_data = df_data[df_data[df_data.columns] < sys.maxsize].dropna()
            df_data = df_data.astype("int32")
            df_data.to_hdf(output_path, key="data", mode="w")

        # Format and export multi-channel data (ECG/PPG)
        df_multidata = self.formatter.format_data(
            data, SchemaRegistry.get_schema(DataType.PHYSIO)
        )
        if not df_multidata.empty:
            # Filter out values that are too large
            df_multidata = df_multidata[
                df_multidata[df_multidata.columns] < sys.maxsize
            ].dropna()
            df_multidata = df_multidata.astype("int32")
            df_multidata.to_hdf(output_path, key="multidata", mode="a")

        # Special handling for IMU data (combined accelerometer and gyroscope)
        df_imu = self.formatter.format_imu_data(data)
        if not df_imu.empty:
            df_imu.to_hdf(output_path, key="imu", mode="a")
        else:
            if logging.getLogger().isEnabledFor(logging.WARNING):
                logging.warning(f"No IMU data: {output_path}")

        # Format and export temperature data
        df_temp = self.formatter.format_data(
            data, SchemaRegistry.get_schema(DataType.TEMPERATURE)
        )
        if not df_temp.empty:
            df_temp.astype("int16").to_hdf(output_path, key="temp", mode="a")

        # Format and export heart rate data
        df_hr = self.formatter.format_data(
            data, SchemaRegistry.get_schema(DataType.HEART_RATE)
        )
        if not df_hr.empty:
            df_hr.astype("int16").to_hdf(output_path, key="hr", mode="a")

        # Format and export AFE settings
        df_afe = self.formatter.format_data(
            data, SchemaRegistry.get_schema(DataType.AFE)
        )
        if not df_afe.empty:
            df_afe.to_hdf(output_path, key="afe", mode="a")

        # Format and export battery diagnostic data
        df_battdiag = self.formatter.format_data(
            data, SchemaRegistry.get_schema(DataType.BATTERY_DIAG)
        )
        if not df_battdiag.empty:
            df_battdiag.to_hdf(output_path, key="battdiag", mode="a")

        # Export device info
        if hasattr(data, "device_info") and data.device_info:
            info = {k: [v] for k, v in asdict(data.device_info).items()}
            pd.DataFrame(info).to_hdf(output_path, key="device_info", mode="a")

        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Converted data to HDF: {output_path}")

    def _export_dataframe(
        self, df: pd.DataFrame, file_path: Path, schema: ExportSchema
    ) -> None:
        """Export a dataframe to HDF.

        This method is only used when explicitly calling export_by_schema.
        The main export method uses a different approach to maintain backward compatibility.

        Args:
            df: The dataframe to export
            file_path: Path where the HDF file should be saved
            schema: The schema used for the export
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        hdf_key = schema.hdf_key or schema.name
        mode = "a" if file_path.exists() else "w"
        df.to_hdf(file_path, key=hdf_key, mode=mode, format="table")

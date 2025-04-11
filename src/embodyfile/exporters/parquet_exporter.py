"""Parquet exporter implementation."""

import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from ..models import Data
from . import BaseExporter


class ParquetExporter(BaseExporter):
    """Exporter for Parquet format with one sensor type per file."""

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to Parquet format with one file per sensor type.

        Args:
            data: The data to export
            output_path: Base path where the Parquet files should be saved
        """
        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Converting data to Parquet format: {output_path}")

        # Create one file per sensor type
        if data.sensor:
            self._export_to_parquet(data.sensor, output_path, "sensor")

        if data.afe:
            self._export_to_parquet(data.afe, output_path, "afe")

        if data.acc:
            self._export_to_parquet(data.acc, output_path, "acc")

        if data.gyro:
            self._export_to_parquet(data.gyro, output_path, "gyro")

        if data.multi_ecg_ppg_data:
            self._export_multidata_to_parquet(
                data.multi_ecg_ppg_data, output_path, "multi_ecg_ppg"
            )

        if data.temp:
            self._export_to_parquet(data.temp, output_path, "temp")

        if data.hr:
            self._export_to_parquet(data.hr, output_path, "hr")

        if data.batt_diag:
            self._export_to_parquet(data.batt_diag, output_path, "battery_diagnostics")

        # Export device info to parquet
        info = {k: [v] for k, v in asdict(data.device_info).items()}
        device_info_path = self._get_output_path(output_path, "device_info")
        pd.DataFrame(info).to_parquet(device_info_path)
        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Exported device info to: {device_info_path}")
            logging.info(f"Exported data to Parquet format: {output_path}")

    def _export_to_parquet(
        self, data: list[tuple[int, Any]], output_path: Path, suffix: str
    ) -> None:
        """Export a single sensor type to a Parquet file.

        Args:
            data: The sensor data to export
            output_path: Base path where the Parquet file should be saved
            suffix: Suffix to add to the filename to identify the sensor type
        """
        if not data:
            return

        df = self._to_pandas(data)
        # Filter out values that are too large
        df = df[df[df.columns] < sys.maxsize].dropna()

        # Determine appropriate data types based on sensor type
        if suffix in ["acc", "gyro", "sensor", "multi_ecg_ppg"]:
            df = df.astype("int32")
        elif suffix in ["temp", "hr"]:
            df = df.astype("int16")

        output_file_path = self._get_output_path(output_path, suffix)
        df.to_parquet(output_file_path)
        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Exported {suffix} data to: {output_file_path}")

    def _export_multidata_to_parquet(
        self, data: list[tuple[int, Any]], output_path: Path, suffix: str
    ) -> None:
        """Export multi-channel data to a Parquet file.

        Args:
            data: The multi-channel data to export
            output_path: Base path where the Parquet file should be saved
            suffix: Suffix to add to the filename to identify the sensor type
        """
        if not data:
            return

        df = self._multi_data2pandas(data)
        # Filter out values that are too large
        df = df[df[df.columns] < sys.maxsize].dropna()
        df = df.astype("int32")

        output_file_path = self._get_output_path(output_path, suffix)
        df.to_parquet(output_file_path)
        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Exported {suffix} data to: {output_file_path}")

        # Additionally, export separate ECG and PPG files if they exist
        ecg_columns = [col for col in df.columns if col.startswith("ecg_")]
        ppg_columns = [col for col in df.columns if col.startswith("ppg_")]

        if ecg_columns:
            ecg_df = df[ecg_columns]
            ecg_output_path = self._get_output_path(output_path, "ecg")
            ecg_df.to_parquet(ecg_output_path)
            if logging.getLogger().isEnabledFor(logging.INFO):
                logging.info(f"Exported ECG data to: {ecg_output_path}")

        if ppg_columns:
            ppg_df = df[ppg_columns]
            ppg_output_path = self._get_output_path(output_path, "ppg")
            ppg_df.to_parquet(ppg_output_path)
            if logging.getLogger().isEnabledFor(logging.INFO):
                logging.info(f"Exported PPG data to: {ppg_output_path}")

    def _get_output_path(self, base_path: Path, suffix: str) -> Path:
        """Create output path with suffix.

        Args:
            base_path: Base path for the output file
            suffix: Suffix to add to the filename

        Returns:
            Path with suffix and .parquet extension
        """
        return base_path.with_stem(f"{base_path.stem}.{suffix}.parquet")

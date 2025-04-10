"""CSV exporter implementation."""

import csv
import logging
from dataclasses import astuple
from dataclasses import fields
from operator import itemgetter
from pathlib import Path

from ..models import Data
from ..parser import _time_str
from . import BaseExporter


class CSVExporter(BaseExporter):
    """Exporter for CSV format."""

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to CSV format.

        Args:
            data: The data to export
            output_path: Path where the CSV file should be saved
        """
        logging.info(f"Exporting data to CSV format: {output_path}")

        self._write_data(self._fname_with_suffix(output_path, "afe"), data.afe)
        self._write_data(self._fname_with_suffix(output_path, "acc"), data.acc)
        self._write_data(self._fname_with_suffix(output_path, "gyro"), data.gyro)
        self._write_data(
            self._fname_with_suffix(output_path, "multi"), data.multi_ecg_ppg_data
        )
        self._write_data(self._fname_with_suffix(output_path, "temp"), data.temp)
        self._write_data(self._fname_with_suffix(output_path, "hr"), data.hr)
        self._write_data(
            self._fname_with_suffix(output_path, "battdiag"), data.batt_diag
        )
        self._write_data(output_path, data.sensor)

        logging.info(f"Exported data to CSV format: {output_path}")

    def _write_data(self, fname: Path, data) -> None:
        """Write data to a CSV file.

        Args:
            fname: Path to the output file
            data: Data to write
        """
        if not data:
            return

        logging.info(f"Writing to: {fname}")
        sorted_data = sorted(data, key=itemgetter(0))
        _, header = sorted_data[0]
        version = None
        from embodycodec import file_codec

        if isinstance(header, file_codec.Header):
            version = tuple(header.firmware_version)
        columns = ["timestamp"] + [f.name for f in fields(sorted_data[0][1])]
        column_data = [(_time_str(ts, version), *astuple(d)) for ts, d in sorted_data]
        with open(fname, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(column_data)

        logging.info(f"Wrote to: {fname}")

    def _fname_with_suffix(self, dst_fname: Path, suffix: str) -> Path:
        """Add a suffix to a filename.

        Args:
            dst_fname: Original file path
            suffix: Suffix to add

        Returns:
            New file path with suffix
        """
        return dst_fname.with_stem(dst_fname.stem + "_" + suffix)

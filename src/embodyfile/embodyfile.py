"""Embody file module to parse binary embody files to various output formats."""

import logging
from pathlib import Path

from .exporters import BaseExporter
from .exporters.csv_exporter import CSVExporter
from .exporters.hdf_legacy_exporter import HDFLegacyExporter
from .exporters.hdf_exporter import HDFExporter
from .exporters.parquet_exporter import ParquetExporter
from .models import Data
from .parser import read_data


def process_file(
    input_path: Path,
    output_path_base: Path,
    output_formats=("HDF_LEGACY",),
    fail_on_errors=False,
) -> None:
    """Process a binary embody file and export it to the specified formats.

    Args:
        input_path: Path to the input binary file
        output_path_base: Base path where the output should be saved
        output_formats: Formats to export the data to (CSV, HDF (legacy), HD5 or Parquet)
        fail_on_errors: Whether to fail on parse errors

    Raises:
        ValueError: If an unsupported output format is specified
    """
    with open(input_path, "rb") as f:
        data = read_data(f, fail_on_errors)
        logging.info(f"Loaded data from: {input_path}")

    # Process each requested output format
    for format_name in output_formats:
        format = format_name.upper()
        output_path = output_path_base.with_suffix("")

        exporter: BaseExporter | None = None
        if format == "CSV":
            exporter = CSVExporter()
        elif format == "HDF_LEGACY":
            exporter = HDFLegacyExporter()
        elif format == "HDF":
            exporter = HDFExporter()
        elif format == "PARQUET":
            exporter = ParquetExporter()
        else:
            raise ValueError(f"Unsupported format: {format}")

        logging.info(f"Exporting to {format} format: {output_path}")
        exporter.export(data, output_path)


def analyse_ppg(data: Data) -> None:
    """Analyze PPG data in the parsed data.

    Args:
        data: The data containing PPG data to analyze
    """
    # Iterate over all ppg channels, count and identify negative values
    logging.info("Analysing PPG data")
    ppg_data = data.multi_ecg_ppg_data
    if not ppg_data:
        logging.warning("No block PPG data found")
        return
    positive = 0
    for _, ppg in ppg_data:
        for ppg_value in ppg.ppgs:
            if ppg_value > 0:
                positive += 1
    logging.info(f"Found {positive} positive PPG values across channels")

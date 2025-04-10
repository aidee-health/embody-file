"""Test cases for the Parquet exporter module."""

import logging
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from embodyfile.exporters.parquet_exporter import ParquetExporter
from embodyfile.parser import read_data


# Configure logging at module level
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s:%(levelname)s:%(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,  # Explicitly output to stdout
    force=True,  # Force reconfiguration of the root logger
)


@pytest.mark.integtest
def test_parquet_export():
    """Test exporting data to Parquet format."""
    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output"

        # Load test data
        with open("testfiles/v5_0_0_test_file.log", "rb") as f:
            data = read_data(f)

        # Export data to Parquet
        exporter = ParquetExporter()
        exporter.export(data, output_path)

        # Check that the files were created with appropriate suffixes
        if len(data.acc) > 0:
            assert (output_path.with_suffix(".acc.parquet")).exists()

        if len(data.gyro) > 0:
            assert (output_path.with_suffix(".gyro.parquet")).exists()

        if len(data.afe) > 0:
            assert (output_path.with_suffix(".afe.parquet")).exists()

        if len(data.multi_ecg_ppg_data) > 0:
            assert (output_path.with_suffix(".multi_ecg_ppg.parquet")).exists()

        # Check that the files contain valid parquet data
        if len(data.acc) > 0:
            df = pd.read_parquet(output_path.with_suffix(".acc.parquet"))
            assert not df.empty
            # Check if timestamp is the index
            assert (
                df.index.name == "timestamp"
            ), f"Expected 'timestamp' as index name but got: {df.index.name}"


@pytest.mark.integtest
def test_parquet_export_multi_ecg_ppg():
    """Test exporting data with multi ECG/PPG to Parquet format."""
    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output"

        # Load test data with multi ECG/PPG
        with open("testfiles/multi-ecg-ppg.log", "rb") as f:
            data = read_data(f)

        # Export data to Parquet
        exporter = ParquetExporter()
        exporter.export(data, output_path)

        # Check that the multi ECG/PPG file was created
        multi_file = output_path.with_suffix(".multi_ecg_ppg.parquet")
        assert multi_file.exists()

        # Check that the file contains valid parquet data
        df = pd.read_parquet(multi_file)
        assert not df.empty

        # Check that timestamp is used as the index
        assert (
            df.index.name == "timestamp"
        ), f"Expected 'timestamp' as index name but got: {df.index.name}"


@pytest.mark.integtest
def test_parquet_export_pulse_block():
    """Test exporting pulse block data to Parquet format."""
    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output"

        # Load test data with pulse block
        with open("testfiles/pulse-block-2-channel-ppg.log", "rb") as f:
            data = read_data(f)

        # Export data to Parquet
        exporter = ParquetExporter()
        exporter.export(data, output_path)

        # Check that the pulse block file was created
        multi_file = output_path.with_suffix(".multi_ecg_ppg.parquet")
        assert multi_file.exists()

        # Check that the file contains valid parquet data
        df = pd.read_parquet(multi_file)
        assert not df.empty
        assert len(df) > 0

"""Test cases for the Parquet exporter module."""

import logging
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from embodyfile.exporters.parquet_exporter import ParquetExporter
from embodyfile.parser import read_data
from tests.test_utils import find_schema_file
from tests.test_utils import get_test_file_path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)


@pytest.mark.integtest
def test_parquet_export():
    """Test exporting data to Parquet format."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output"

        test_file_path = get_test_file_path("v5_0_0_test_file.log")

        with open(test_file_path, "rb") as f:
            data = read_data(f)

        exporter = ParquetExporter()
        exporter.export(data, output_path)

        afe_file = find_schema_file(temp_dir, "test_output", "afe", "parquet")
        acc_file = find_schema_file(temp_dir, "test_output", "acc", "parquet")
        gyro_file = find_schema_file(temp_dir, "test_output", "gyro", "parquet")
        ecgppg_file = find_schema_file(temp_dir, "test_output", "ecgppg", "parquet")

        if len(data.acc) > 0:
            assert acc_file.exists()

        if len(data.gyro) > 0:
            assert gyro_file.exists()

        if len(data.afe) > 0:
            assert afe_file.exists()

        if len(data.multi_ecg_ppg_data) > 0:
            assert ecgppg_file.exists()

        if len(data.acc) > 0:
            df = pd.read_parquet(acc_file)
            assert not df.empty
            assert (
                "timestamp" in df.columns
            ), f"Expected 'timestamp' column but got: {df.columns}"


@pytest.mark.integtest
def test_parquet_export_multi_ecg_ppg():
    """Test exporting data with multi ECG/PPG to Parquet format."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output"

        test_file_path = get_test_file_path("multi-ecg-ppg.log")

        with open(test_file_path, "rb") as f:
            data = read_data(f)
        exporter = ParquetExporter()
        exporter.export(data, output_path)

        multi_file = find_schema_file(temp_dir, "test_output", "ecgppg", "parquet")
        assert multi_file.exists()

        df = pd.read_parquet(multi_file)
        assert not df.empty

        assert (
            "timestamp" in df.columns
        ), f"Expected 'timestamp' column but got: {df.columns}"


@pytest.mark.integtest
def test_parquet_export_pulse_block():
    """Test exporting pulse block data to Parquet format."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output"

        with open(get_test_file_path("pulse-block-2-channel-ppg.log"), "rb") as f:
            data = read_data(f)

        exporter = ParquetExporter()
        exporter.export(data, output_path)

        multi_file = find_schema_file(temp_dir, "test_output", "ecgppg", "parquet")
        assert multi_file.exists()

        df = pd.read_parquet(multi_file)
        assert not df.empty
        assert len(df) > 0

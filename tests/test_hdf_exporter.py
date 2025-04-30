"""Test cases for the modern HDF exporter module."""

import logging
import sys
import tempfile
from pathlib import Path

import h5py
import pandas as pd
import pytest

from embodyfile.exporters.hdf_exporter import HDFExporter
from embodyfile.parser import read_data
from tests.test_utils import get_test_file_path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)


@pytest.mark.integtest
def test_hdf_export():
    """Test exporting data to HDF format."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output.hdf5"

        test_file_path = get_test_file_path("v5_0_0_test_file.log")

        with open(test_file_path, "rb") as f:
            data = read_data(f)

        exporter = HDFExporter()
        exporter.export(data, output_path)

        assert output_path.exists()

        with h5py.File(output_path, "r") as f:
            # Print all top-level groups and datasets
            logging.info(f"HDF5 file contents: {list(f.keys())}")
            assert "ecgppg" in f, f"ecgppg group not found in {list(f.keys())}"
            assert "acc" in f, f"acc group not found in {list(f.keys())}"
            assert "gyro" in f, f"gyro group not found in {list(f.keys())}"

            # Verify data was stored correctly
            if len(data.acc) > 0:
                acc_data = pd.read_hdf(output_path, "acc")
                assert not acc_data.empty
                assert "acc_x" in acc_data.columns

            if len(data.multi_ecg_ppg_data) > 0:
                ecgppg_data = pd.read_hdf(output_path, "ecgppg")
                assert not ecgppg_data.empty
                assert "ecg" in ecgppg_data.columns


@pytest.mark.integtest
def test_hdf_export_multi_ecg_ppg():
    """Test exporting data with multi ECG/PPG to HDF format."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output.hdf5"

        test_file_path = get_test_file_path("multi-ecg-ppg.log")

        with open(test_file_path, "rb") as f:
            data = read_data(f)

        exporter = HDFExporter()
        exporter.export(data, output_path)

        assert output_path.exists()

        with h5py.File(output_path, "r") as f:
            logging.info(f"HDF5 file contents for multi ECG/PPG: {list(f.keys())}")
            assert "ecgppg" in f, f"ecgppg group not found in {list(f.keys())}"

            # Verify data was loaded correctly
            ecgppg_data = pd.read_hdf(output_path, "ecgppg")
            assert not ecgppg_data.empty
            assert "ecg" in ecgppg_data.columns


@pytest.mark.integtest
def test_hdf_export_schema_filtering():
    """Test exporting data with schema filtering."""
    from embodyfile.schemas import DataType

    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_filtered_output.hdf5"

        test_file_path = get_test_file_path("v5_0_0_test_file.log")

        with open(test_file_path, "rb") as f:
            data = read_data(f)

        exporter = HDFExporter()
        # Only export ACC and GYRO data
        exporter.set_schema_filter([DataType.ACCELEROMETER, DataType.GYROSCOPE])
        exporter.export(data, output_path)

        assert output_path.exists()

        with h5py.File(output_path, "r") as f:
            keys = list(f.keys())
            logging.info(f"HDF5 file contents with filter: {keys}")

            # Should contain ACC and GYRO data
            assert "acc" in keys
            assert "gyro" in keys

            # Should NOT contain ECG/PPG data
            assert "ecgppg" not in keys

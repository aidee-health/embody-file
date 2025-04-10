"""Test cases for the HDF exporter module."""

import logging
import sys
import tempfile
from pathlib import Path

import h5py
import pytest

from embodyfile.exporters.hdf_exporter import HDFExporter
from embodyfile.parser import read_data


# Configure logging at module level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,  # Explicitly output to stdout
    force=True,  # Force reconfiguration of the root logger
)


@pytest.mark.integtest
def test_hdf_export():
    """Test exporting data to HDF format."""
    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output.hdf"

        # Load test data
        with open("testfiles/v5_0_0_test_file.log", "rb") as f:
            data = read_data(f)

        # Export data to HDF
        exporter = HDFExporter()
        exporter.export(data, output_path)

        # Check that the file was created
        assert output_path.exists()

        # Check what's actually in the file
        with h5py.File(output_path, "r") as f:
            # Print all top-level groups and datasets
            logging.info(f"HDF5 file contents: {list(f.keys())}")

            # Check for IMU data (accelerometer and gyroscope)
            assert "imu" in f, f"IMU dataset not found in {list(f.keys())}"
            assert len(f["imu"]) > 0, "IMU dataset is empty"

            # Check for AFE settings
            if len(data.afe) > 0:
                assert "afe" in f, f"AFE dataset not found in {list(f.keys())}"
                assert len(f["afe"]) > 0, "AFE dataset is empty"


@pytest.mark.integtest
def test_hdf_export_multi_ecg_ppg():
    """Test exporting data with multi ECG/PPG to HDF format."""
    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output.hdf"

        # Load test data with multi ECG/PPG
        with open("testfiles/multi-ecg-ppg.log", "rb") as f:
            data = read_data(f)

        # Export data to HDF
        exporter = HDFExporter()
        exporter.export(data, output_path)

        # Check that the file was created
        assert output_path.exists()

        # Check what's actually in the file
        with h5py.File(output_path, "r") as f:
            logging.info(f"HDF5 file contents for multi ECG/PPG: {list(f.keys())}")

            # Check for multidata (which likely contains the multi ECG/PPG data)
            assert "multidata" in f, f"multidata dataset not found in {list(f.keys())}"
            assert len(f["multidata"]) > 0, "multidata dataset is empty"

            # Additional checks for IMU and other data
            if len(data.acc) > 0:
                assert "imu" in f, f"IMU dataset not found in {list(f.keys())}"
                assert len(f["imu"]) > 0, "IMU dataset is empty"

            if len(data.afe) > 0:
                assert "afe" in f, f"AFE dataset not found in {list(f.keys())}"
                assert len(f["afe"]) > 0, "AFE dataset is empty"

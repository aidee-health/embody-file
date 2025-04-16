"""Test cases for the HDF exporter module."""

import logging
import sys
import tempfile
from pathlib import Path

import h5py
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
        output_path = temp_dir / "test_output.hdf"

        test_file_path = get_test_file_path("v5_0_0_test_file.log")

        with open(test_file_path, "rb") as f:
            data = read_data(f)

        exporter = HDFExporter()
        exporter.export(data, output_path)

        assert output_path.exists()

        with h5py.File(output_path, "r") as f:
            # Print all top-level groups and datasets
            logging.info(f"HDF5 file contents: {list(f.keys())}")

            assert "imu" in f, f"IMU dataset not found in {list(f.keys())}"
            assert len(f["imu"]) > 0, "IMU dataset is empty"

            if len(data.afe) > 0:
                assert "afe" in f, f"AFE dataset not found in {list(f.keys())}"
                assert len(f["afe"]) > 0, "AFE dataset is empty"


@pytest.mark.integtest
def test_hdf_export_multi_ecg_ppg():
    """Test exporting data with multi ECG/PPG to HDF format."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output.hdf"

        test_file_path = get_test_file_path("multi-ecg-ppg.log")

        with open(test_file_path, "rb") as f:
            data = read_data(f)

        exporter = HDFExporter()
        exporter.export(data, output_path)

        assert output_path.exists()

        with h5py.File(output_path, "r") as f:
            logging.info(f"HDF5 file contents for multi ECG/PPG: {list(f.keys())}")

            assert "multidata" in f, f"multidata dataset not found in {list(f.keys())}"
            assert len(f["multidata"]) > 0, "multidata dataset is empty"

            if len(data.acc) > 0:
                assert "imu" in f, f"IMU dataset not found in {list(f.keys())}"
                assert len(f["imu"]) > 0, "IMU dataset is empty"

            if len(data.afe) > 0:
                assert "afe" in f, f"AFE dataset not found in {list(f.keys())}"
                assert len(f["afe"]) > 0, "AFE dataset is empty"


@pytest.mark.integtest
def test_hdf_export_legacy_sensor_data():
    """Test exporting data with legacy ECG/PPG to HDF format."""
    logging.info("Starting HDF export sensor ECG/PPG test")

    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output.hdf"

        test_file_path = get_test_file_path("v3_9_0_test_file.log")
        with open(test_file_path, "rb") as f:
            data = read_data(f)

        exporter = HDFExporter()
        exporter.export(data, output_path)

        assert output_path.exists()

        with h5py.File(output_path, "r") as f:
            logging.info(f"HDF5 file contents for multi ECG/PPG: {list(f.keys())}")

            assert "multidata" in f, f"multidata dataset not found in {list(f.keys())}"
            assert len(f["multidata"]) > 0, "multidata dataset is empty"

            if len(data.acc) > 0:
                assert "imu" in f, f"IMU dataset not found in {list(f.keys())}"
                assert len(f["imu"]) > 0, "IMU dataset is empty"

            if len(data.afe) > 0:
                assert "afe" in f, f"AFE dataset not found in {list(f.keys())}"
                assert len(f["afe"]) > 0, "AFE dataset is empty"

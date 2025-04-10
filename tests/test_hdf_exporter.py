"""Test cases for the HDF exporter module."""

import tempfile
from pathlib import Path

import h5py
import pytest

from embodyfile.exporters.hdf_exporter import HDFExporter
from embodyfile.parser import read_data


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

        # Check that the file has the expected structure
        with h5py.File(output_path, "r") as f:
            # Check for expected datasets/groups
            if len(data.acc) > 0:
                assert "acc" in f
                assert len(f["acc"]) > 0

            if len(data.gyro) > 0:
                assert "gyro" in f
                assert len(f["gyro"]) > 0

            if len(data.afe) > 0:
                assert "afe" in f
                assert len(f["afe"]) > 0

            if len(data.multi_ecg_ppg_data) > 0:
                assert "multi_ecg_ppg" in f
                assert len(f["multi_ecg_ppg"]) > 0


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

        # Check that the file has the expected structure for multi ECG/PPG data
        with h5py.File(output_path, "r") as f:
            assert "multi_ecg_ppg" in f

            # Check if there's data in the dataset
            assert len(f["multi_ecg_ppg"]) > 0

            # Check that the dataset has the expected attributes
            assert "timestamp" in f["multi_ecg_ppg"]

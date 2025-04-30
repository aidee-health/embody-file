"""Test cases for the HDF exporter module."""

import logging
import sys
import tempfile
from pathlib import Path

import h5py
import pytest

from embodyfile.exporters.hdf_legacy_exporter import HDFLegacyExporter
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

        exporter = HDFLegacyExporter()
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

            assert "device_info" in f, f"Device info dataset not found in {list(f.keys())}"
            assert len(f["device_info"]) > 0, "Device info dataset is empty"


@pytest.mark.integtest
def test_hdf_export_multi_ecg_ppg():
    """Test exporting data with multi ECG/PPG to HDF format."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output.hdf"

        test_file_path = get_test_file_path("multi-ecg-ppg.log")

        with open(test_file_path, "rb") as f:
            data = read_data(f)

        exporter = HDFLegacyExporter()
        exporter.export(data, output_path)

        assert output_path.exists()

        with h5py.File(output_path, "r") as f:
            logging.info(f"HDF5 file contents for multi ECG/PPG: {list(f.keys())}")

            assert "multidata" in f, f"multidata dataset not found in {list(f.keys())}"
            assert len(f["multidata"]) > 0, "multidata dataset is empty"
            examine_hdf_pandas_dataframe(output_path, "multidata")

            if len(data.acc) > 0:
                assert "imu" in f, f"IMU dataset not found in {list(f.keys())}"
                assert len(f["imu"]) > 0, "IMU dataset is empty"

            if len(data.afe) > 0:
                assert "afe" in f, f"AFE dataset not found in {list(f.keys())}"
                assert len(f["afe"]) > 0, "AFE dataset is empty"

            assert "device_info" in f, f"Device info dataset not found in {list(f.keys())}"
            assert len(f["device_info"]) > 0, "Device info dataset is empty"


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

        exporter = HDFLegacyExporter()
        exporter.export(data, output_path)

        assert output_path.exists()

        with h5py.File(output_path, "r") as f:
            logging.info(f"HDF5 file contents for multi ECG/PPG: {list(f.keys())}")

            assert "data" in f, f"data dataset not found in {list(f.keys())}"
            assert len(f["data"]) > 0, "data dataset is empty"
            # Log detailed info about the multidata and dataset
            examine_hdf_pandas_dataframe(output_path, "multidata")
            examine_hdf_pandas_dataframe(output_path, "data")

            if len(data.acc) > 0:
                assert "imu" in f, f"IMU dataset not found in {list(f.keys())}"
                assert len(f["imu"]) > 0, "IMU dataset is empty"

            if len(data.afe) > 0:
                assert "afe" in f, f"AFE dataset not found in {list(f.keys())}"
                assert len(f["afe"]) > 0, "AFE dataset is empty"

            assert "device_info" in f, f"Device info dataset not found in {list(f.keys())}"
            assert len(f["device_info"]) > 0, "Device info dataset is empty"


def examine_hdf_pandas_dataframe(file_path: Path, key: str, sample_rows: int = 5) -> None:
    """Examine a Pandas DataFrame stored in an HDF5 file."""
    import pandas as pd

    logging.info(f"Reading pandas DataFrame from {file_path} with key {key}")

    try:
        # Load the DataFrame using Pandas
        df = pd.read_hdf(file_path, key=key)

        # Log DataFrame info
        logging.info(f"========== {key} (Pandas DataFrame) ==========")
        logging.info(f"Shape: {df.shape}")
        logging.info(f"Columns: {list(df.columns)}")
        logging.info(f"Index type: {type(df.index)}")
        if hasattr(df.index, "dtype"):
            logging.info(f"Index dtype: {df.index.dtype}")

        # Log column types
        logging.info("Column types:")
        for col, dtype in df.dtypes.items():
            logging.info(f"  {col}: {dtype}")

        # Show sample data
        if not df.empty and sample_rows > 0:
            logging.info(f"Sample data (first {min(sample_rows, len(df))} rows):")
            pd.set_option("display.max_columns", None)
            logging.info(f"\n{df.head(sample_rows)}")

        logging.info("=" * (25 + len(key)))
        return df

    except Exception as e:
        logging.error(f"Error loading pandas DataFrame: {e}")
        return None

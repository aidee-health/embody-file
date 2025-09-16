"""Test cases for the HDF exporter module."""

import logging
import tempfile
from pathlib import Path

import h5py
import pandas as pd
import pytest

from embodyfile.exporters.hdf_legacy_exporter import HDFLegacyExporter
from embodyfile.parser import read_data
from tests.test_utils import get_test_file_path

logger = logging.getLogger(__name__)


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
            logger.info(f"HDF5 file contents: {list(f.keys())}")

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
        df_multidata = pd.read_hdf(output_path, key="multidata")
        assert isinstance(df_multidata, pd.DataFrame), "multidata is not a DataFrame"
        assert not df_multidata.empty, "multidata DataFrame is empty"
        # assert df_multidata.index.freq == pd.Timedelta("1ms"), "multidata index frequency is not 1ms"

        with h5py.File(output_path, "r") as f:
            logger.info(f"HDF5 file contents for multi ECG/PPG: {list(f.keys())}")

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
def test_multi_block_ecg_2_channel_ppg():
    """Test exporting data with multi block ECG/PPG to HDF format."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output.hdf"

        test_file_path = get_test_file_path("pulse-block-2-channel-ppg.log")

        with open(test_file_path, "rb") as f:
            data = read_data(f)

        exporter = HDFLegacyExporter()
        exporter.export(data, output_path)
        assert output_path.exists()
        df_multidata = pd.read_hdf(output_path, key="multidata")
        assert isinstance(df_multidata, pd.DataFrame), "multidata is not a DataFrame"
        assert not df_multidata.empty, "multidata DataFrame is empty"

        # Check that frequency is stored as metadata
        with pd.HDFStore(output_path, mode="r") as store:
            attrs = store.get_storer("multidata").attrs
            assert hasattr(attrs, "sample_frequency_hz"), "sample_frequency_hz not in metadata"
            assert attrs.sample_frequency_hz == 1000, f"Expected 1000 Hz, got {attrs.sample_frequency_hz}"
            assert hasattr(attrs, "sample_period_ms"), "sample_period_ms not in metadata"
            assert attrs.sample_period_ms == 1.0, f"Expected 1.0 ms, got {attrs.sample_period_ms}"


@pytest.mark.integtest
def test_hdf_export_legacy_sensor_data():
    """Test exporting data with legacy ECG/PPG to HDF format."""
    logger.info("Starting HDF export sensor ECG/PPG test")

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
            logger.info(f"HDF5 file contents for multi ECG/PPG: {list(f.keys())}")

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
    logger.info(f"Reading pandas DataFrame from {file_path} with key {key}")

    try:
        # Load the DataFrame using Pandas
        df = pd.read_hdf(file_path, key=key)

        # Log DataFrame info
        logger.info(f"========== {key} (Pandas DataFrame) ==========")
        logger.info(f"Shape: {df.shape}")
        logger.info(f"Columns: {list(df.columns)}")
        logger.info(f"Index type: {type(df.index)}")
        if hasattr(df.index, "dtype"):
            logger.info(f"Index dtype: {df.index.dtype}")

        # Check for frequency metadata
        with pd.HDFStore(file_path, mode="r") as store:
            if key in store:
                attrs = store.get_storer(key).attrs
                if hasattr(attrs, "sample_frequency_hz"):
                    logger.info(f"Sample frequency (from metadata): {attrs.sample_frequency_hz} Hz")
                if hasattr(attrs, "sample_period_ms"):
                    logger.info(f"Sample period (from metadata): {attrs.sample_period_ms} ms")

        # Log column types
        logger.info("Column types:")
        for col, dtype in df.dtypes.items():
            logger.info(f"  {col}: {dtype}")

        # Show sample data
        if not df.empty and sample_rows > 0:
            logger.info(f"Sample data (first {min(sample_rows, len(df))} rows):")
            pd.set_option("display.max_columns", None)
            logger.info(f"\n{df.head(sample_rows)}")

        logger.info("=" * (25 + len(key)))
        return df

    except Exception as e:
        logger.error(f"Error loading pandas DataFrame: {e}")
        return None

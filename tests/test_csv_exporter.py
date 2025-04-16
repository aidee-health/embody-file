"""Test cases for the CSV exporter module."""

import csv
import logging
import sys
import tempfile
from pathlib import Path

import pytest

from embodyfile.exporters.csv_exporter import CSVExporter
from embodyfile.parser import read_data
from tests.test_utils import find_schema_file
from tests.test_utils import get_test_file_path


# Configure logging at module level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,  # Explicitly output to stdout
    force=True,  # Force reconfiguration of the root logger
)


@pytest.mark.integtest
def test_csv_export():
    """Test exporting data to CSV format."""
    logging.info("Starting CSV export test")

    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output"
        logging.info(f"Temporary output path: {output_path}")

        test_file_path = get_test_file_path("v5_0_0_test_file.log")
        logging.info(f"Loading test data from {test_file_path}")

        with open(test_file_path, "rb") as f:
            data = read_data(f)
        logging.info(
            f"Data loaded successfully. Contains {len(data.sensor)} sensor records"
        )

        # Export data to CSV
        logging.info("Exporting data to CSV")
        exporter = CSVExporter()
        exporter.export(data, output_path)

        # Check that the files were created
        logging.info("Checking if output files were created")
        afe_file = find_schema_file(temp_dir, "test_output", "afe", "csv")
        acc_file = find_schema_file(temp_dir, "test_output", "acc", "csv")
        gyro_file = find_schema_file(temp_dir, "test_output", "gyro", "csv")

        logging.info(f"Checking AFE file: {afe_file}")
        assert afe_file.exists(), f"AFE file {afe_file} does not exist"

        logging.info(f"Checking ACC file: {acc_file}")
        assert acc_file.exists(), f"ACC file {acc_file} does not exist"

        logging.info(f"Checking GYRO file: {gyro_file}")
        assert gyro_file.exists(), f"GYRO file {gyro_file} does not exist"

        # If there is multi ECG/PPG data, check that file was created
        if data.multi_ecg_ppg_data:
            multi_file = output_path.with_suffix(".multi.csv")
            logging.info(f"Checking MULTI file: {multi_file}")
            assert multi_file.exists(), f"MULTI file {multi_file} does not exist"
        else:
            logging.info("No multi ECG/PPG data, skipping multi file check")

        # Check that the files have content
        logging.info("Checking file contents")
        try:
            with open(acc_file) as csv_file:
                reader = csv.reader(csv_file)
                # Skip header
                header = next(reader, None)
                logging.info(f"ACC file header: {header}")
                # Check if there's data in the file
                row = next(reader, None)
                logging.info(f"ACC file first data row: {row}")
                assert row is not None, "ACC file has no data rows"

            # Check that the files have the expected structure (e.g., for acc data)
            with open(acc_file) as csv_file:
                reader = csv.reader(csv_file)
                header = next(reader, None)
                assert (
                    "timestamp" in header[0].lower()
                ), f"Expected 'timestamp' in header but got: {header[0]}"
        except Exception as e:
            logging.error(f"Error checking file contents: {e}")
            raise


@pytest.mark.integtest
def test_csv_export_legacy_sensor_data():
    """Test exporting data with legacy ECG/PPG to CSV format."""
    logging.info("Starting CSV export sensor ECG/PPG test")

    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output"
        logging.info(f"Temporary output path: {output_path}")

        test_file_path = get_test_file_path("v3_9_0_test_file.log")
        logging.info(f"Loading test data from {test_file_path}")

        with open(test_file_path, "rb") as f:
            data = read_data(f)
        logging.info(
            f"Data loaded successfully. Contains {len(data.sensor)} sensor ECG/PPG records"
        )

        # Export data to CSV
        logging.info("Exporting data to CSV")
        exporter = CSVExporter()
        exporter.export(data, output_path)

        sensor_file = find_schema_file(temp_dir, "test_output", "ecgppg", "csv")
        logging.info(f"Checking if sensor file exists: {sensor_file}")
        assert sensor_file.exists(), f"Sensor file {sensor_file} does not exist"

        # Check that the sensor file has content
        logging.info("Checking sensor file contents")
        try:
            with open(sensor_file) as csv_file:
                reader = csv.reader(csv_file)
                # Skip header
                header = next(reader, None)
                logging.info(f"Sensor file header: {header}")
                # Check if there's data in the file
                row = next(reader, None)
                logging.info(f"Sensor file first data row: {row}")
                assert row is not None, "Sensor file has no data rows"
        except Exception as e:
            logging.error(f"Error checking sensor file contents: {e}")
            raise


@pytest.mark.integtest
def test_csv_export_multi_ecg_ppg():
    """Test exporting data with multi ECG/PPG to CSV format."""
    logging.info("Starting CSV export multi ECG/PPG test")

    # Create a temporary directory for output files
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_dir = Path(tmpdirname)
        output_path = temp_dir / "test_output"
        logging.info(f"Temporary output path: {output_path}")

        test_file_path = get_test_file_path("multi-ecg-ppg.log")
        logging.info(f"Loading test data from {test_file_path}")

        with open(test_file_path, "rb") as f:
            data = read_data(f)
        logging.info(
            f"Data loaded successfully. Contains {len(data.multi_ecg_ppg_data)} multi ECG/PPG records"
        )

        # Export data to CSV
        logging.info("Exporting data to CSV")
        exporter = CSVExporter()
        exporter.export(data, output_path)

        # Check that the multi file was created
        multi_file = find_schema_file(temp_dir, "test_output", "ecgppg", "csv")
        logging.info(f"Checking if multi file exists: {multi_file}")
        assert multi_file.exists(), f"Multi file {multi_file} does not exist"

        # Check that the multi file has content
        logging.info("Checking multi file contents")
        try:
            with open(multi_file) as csv_file:
                reader = csv.reader(csv_file)
                # Skip header
                header = next(reader, None)
                logging.info(f"Multi file header: {header}")
                # Check if there's data in the file
                row = next(reader, None)
                logging.info(f"Multi file first data row: {row}")
                assert row is not None, "Multi file has no data rows"
        except Exception as e:
            logging.error(f"Error checking multi file contents: {e}")
            raise

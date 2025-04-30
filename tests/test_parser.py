"""Test cases for the parser module."""

import pytest

from embodyfile.models import Data
from embodyfile.parser import read_data
from tests.test_utils import get_test_file_path


def test_dummy():
    pass


@pytest.mark.integtest
def test_read_data_v500():
    """Test parsing of v5.0.0 format log file."""
    with open(get_test_file_path("v5_0_0_test_file.log"), "rb") as f:
        data = read_data(f)
        assert isinstance(data, Data)
        assert len(data.sensor) == 10639
        assert len(data.afe) == 1
        assert len(data.gyro) == 276
        assert len(data.acc) == 276


@pytest.mark.integtest
def test_read_data_v390():
    """Test parsing of v3.9.0 format log file."""
    with open(get_test_file_path("v3_9_0_test_file.log"), "rb") as f:
        data = read_data(f)
        assert isinstance(data, Data)
        assert len(data.sensor) == 10654
        assert len(data.afe) == 2
        assert len(data.gyro) == 265
        assert len(data.acc) == 265


@pytest.mark.integtest
def test_read_data_multi_ecg_ppg():
    """Test parsing of multi-ecg-ppg log file."""
    with open(get_test_file_path("multi-ecg-ppg.log"), "rb") as f:
        data = read_data(f)
        assert isinstance(data, Data)
        assert len(data.multi_ecg_ppg_data) == 72
        assert data.sensor == []
        assert len(data.afe) == 1
        assert len(data.gyro) == 3
        assert len(data.acc) == 19


@pytest.mark.integtest
def test_read_data_multi_block_ecg_ppg():
    """Test parsing of v5.4.0 pulse block messages log file."""
    with open(get_test_file_path("v5_4_0_pulse_block_messages.log"), "rb") as f:
        data = read_data(f)
        assert isinstance(data, Data)
        assert len(data.multi_ecg_ppg_data) == 3795
        assert data.sensor == []
        assert len(data.afe) == 1
        assert len(data.gyro) == 93
        assert len(data.acc) == 716


@pytest.mark.integtest
def test_read_data_multi_block_ecg_2_channel_ppg():
    """Test parsing of pulse-block-2-channel-ppg log file."""
    with open(get_test_file_path("pulse-block-2-channel-ppg.log"), "rb") as f:
        data = read_data(f)
        assert isinstance(data, Data)
        assert len(data.multi_ecg_ppg_data) == 6765
        assert data.sensor == []
        assert len(data.afe) == 1
        assert len(data.gyro) == 178
        assert len(data.acc) == 1380


@pytest.mark.integtest
def test_read_data_with_errors():
    """Test that parsing erroneous file raises LookupError."""
    with pytest.raises(LookupError):
        with open(get_test_file_path("erroneous.log"), "rb") as f:
            read_data(f)


@pytest.mark.integtest
def test_read_data_with_samplerate():
    """Test parsing with different samplerates."""
    samplerates = ["1000", "500", "250", "125"]

    for rate in samplerates:
        with open(get_test_file_path("v5_0_0_test_file.log"), "rb") as f:
            data = read_data(f, samplerate=rate)
            assert isinstance(data, Data)
            # The actual test would depend on how samplerate affects the data
            # This simple test just verifies that parsing completes without errors

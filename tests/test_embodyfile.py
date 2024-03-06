"""Test cases for the embodyfile module."""

import pytest

from embodyfile import embodyfile


def test_dummy():
    pass


@pytest.mark.integtest
def test_v500_logfile():
    with open("testfiles/v5_0_0_test_file.log", "rb") as f:
        data = embodyfile.read_data(f)
        assert len(data.sensor) == 10639
        assert len(data.afe) == 1
        assert len(data.gyro) == 276
        assert len(data.acc) == 276


@pytest.mark.integtest
def test_v390_logfile():
    with open("testfiles/v3_9_0_test_file.log", "rb") as f:
        data = embodyfile.read_data(f)
        assert len(data.sensor) == 10654
        assert len(data.afe) == 2
        assert len(data.gyro) == 265
        assert len(data.acc) == 265


@pytest.mark.integtest
def test_multi_ecg_ppg_type():
    with open("testfiles/multi-ecg-ppg.log", "rb") as f:
        data = embodyfile.read_data(f)
        assert len(data.multi_ecg_ppg_data) == 72
        assert data.sensor == []
        assert len(data.afe) == 1
        assert len(data.gyro) == 3
        assert len(data.acc) == 19


@pytest.mark.integtest
def test_multi_block_ecg_ppg_type():
    with open("testfiles/v5_4_0_pulse_block_messages.log", "rb") as f:
        data = embodyfile.read_data(f)
        assert len(data.multi_ecg_ppg_data) == 3786
        assert data.sensor == []
        assert len(data.afe) == 1
        assert len(data.gyro) == 93
        assert len(data.acc) == 716


@pytest.mark.integtest
def test_multi_block_ecg_2_channel_ppg():
    with open("testfiles/pulse-block-2-channel-ppg.log", "rb") as f:
        data = embodyfile.read_data(f)
        assert len(data.multi_ecg_ppg_data) == 6749
        assert data.sensor == []
        assert len(data.afe) == 1
        assert len(data.gyro) == 178
        assert len(data.acc) == 1380


@pytest.mark.integtest
def test_erroneous_file():
    with pytest.raises(LookupError):
        with open("testfiles/erroneous.log", "rb") as f:
            embodyfile.read_data(f)

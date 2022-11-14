"""Test cases for the embodyfile module."""
from embodyfile import embodyfile


def test_v500_logfile(self):
    with open("testfiles/v5_0_0_test_file.log", "rb") as f:
        data = embodyfile.read_data(f)
        assert len(data.sensor) == 10639
        assert len(data.afe) == 1
        assert len(data.gyro) == 276
        assert len(data.acc) == 276


def test_v390_logfile(self):
    with open("testfiles/v3_9_0_test_file.log", "rb") as f:
        data = embodyfile.read_data(f)
        assert len(data.sensor) == 10654
        assert len(data.afe) == 2
        assert len(data.gyro) == 265
        assert len(data.acc) == 265


def test_multi_ecg_ppg_type(self):
    with open("testfiles/multi-ecg-ppg.log", "rb") as f:
        data = embodyfile.read_data(f)
        assert len(data.multi_ecg_ppg_data) == 72
        assert data.sensor == []
        assert len(data.afe) == 1
        assert len(data.gyro) == 3
        assert len(data.acc) == 19

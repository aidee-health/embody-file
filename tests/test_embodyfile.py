"""Test cases for the embodyfile module."""
import unittest

from embodyfile import embodyfile


class TestDecoder(unittest.TestCase):
    def test_v500_logfile(self):
        with open("testfiles/v5_0_0_test_file.log", "rb") as f:
            data = embodyfile.read_data(f)
            self.assertEqual(len(data.sensor), 10639, "Invalid amount of sensor data")
            self.assertEqual(len(data.afe), 1, "Invalid amount afe settings data")
            self.assertEqual(len(data.gyro), 276, "Invalid amount gyro settings data")
            self.assertEqual(len(data.acc), 276, "Invalid amount acc settings data")

    def test_v390_logfile(self):
        with open("testfiles/v3_9_0_test_file.log", "rb") as f:
            data = embodyfile.read_data(f)
            self.assertEqual(len(data.sensor), 10654, "Invalid amount of sensor data")
            self.assertEqual(len(data.afe), 2, "Invalid amount afe settings data")
            self.assertEqual(len(data.gyro), 265, "Invalid amount gyro settings data")
            self.assertEqual(len(data.acc), 265, "Invalid amount acc settings data")

    def test_multi_ecg_ppg_type(self):
        with open("testfiles/multi-ecg-ppg.log", "rb") as f:
            data = embodyfile.read_data(f)
            self.assertEqual(
                len(data.multi_ecg_ppg_data), 72, "Invalid amount of sensor data"
            )
            self.assertEqual(data.sensor, [], "Invalid amount of sensor data")
            self.assertEqual(len(data.afe), 1, "Invalid amount afe settings data")
            self.assertEqual(len(data.gyro), 3, "Invalid amount gyro settings data")
            self.assertEqual(len(data.acc), 19, "Invalid amount acc settings data")

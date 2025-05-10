"""Parser utilities tests."""

from datetime import datetime

from embodyfile.parser_utils import time_str, serial_no_to_hex, TIMEZONE_OSLO


class TestTimeStr:
    def test_time_str_utc_default_version_none(self):
        # Timestamp: 2023-03-15 12:00:00.000 UTC
        time_in_millis = 1678881600000
        expected_str = "2023-03-15T12:00:00.000"
        assert time_str(time_in_millis, None) == expected_str

    def test_time_str_utc_newer_version(self):
        # Timestamp: 2023-03-15 12:00:00.000 UTC
        time_in_millis = 1678881600000
        version = (5, 3, 10)  # > (5, 3, 9)
        expected_str = "2023-03-15T12:00:00.000"
        assert time_str(time_in_millis, version) == expected_str

    def test_time_str_oslo_older_version(self):
        # Timestamp: 2023-03-15 12:00:00.000 UTC
        # Oslo is UTC+1 in March (CET)
        time_in_millis = 1678881600000
        version = (5, 3, 9)  # <= (5, 3, 9)
        # Expected: 2023-03-15 13:00:00.000 (Oslo time)
        expected_str = "2023-03-15T13:00:00.000"
        assert time_str(time_in_millis, version) == expected_str

    def test_time_str_oslo_exact_version_match(self):
        time_in_millis = 1678881600000  # 2023-03-15 12:00:00 UTC
        version = (5, 3, 9)
        # Oslo is UTC+1 in March (CET) -> 13:00:00
        expected_dt = datetime.fromtimestamp(time_in_millis / 1000, tz=TIMEZONE_OSLO)
        expected_str = expected_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        assert time_str(time_in_millis, version) == expected_str

    def test_time_str_oslo_older_version_summer(self):
        # Timestamp: 2023-07-15 12:00:00.000 UTC
        # Oslo is UTC+2 in July (CEST)
        time_in_millis = 1689422400000
        version = (5, 3, 0)  # <= (5, 3, 9)
        # Expected: 2023-07-15 14:00:00.000 (Oslo time)
        expected_str = "2023-07-15T14:00:00.000"
        assert time_str(time_in_millis, version) == expected_str

    def test_time_str_exception(self):
        # Using a timestamp that might cause an error, e.g., too large for some systems
        # or a type that fromtimestamp cannot handle (though type hint is int)
        # The function catches generic Exception.
        # A very large number might cause OverflowError before strftime.
        time_in_millis = 10**18  # A very large number of milliseconds
        expected_str = "????-??-??T??:??:??.???"
        assert time_str(time_in_millis, None) == expected_str

    def test_time_str_zero_millis(self):
        time_in_millis = 0  # Corresponds to 1970-01-01 00:00:00 UTC
        expected_str_utc = "1970-01-01T00:00:00.000"
        # Oslo was UTC+1 in Jan 1970
        expected_str_oslo = "1970-01-01T01:00:00.000"
        assert time_str(time_in_millis, None) == expected_str_utc
        assert time_str(time_in_millis, (5, 0, 0)) == expected_str_oslo


# Tests for _serial_no_to_hex
class TestSerialNoToHex:
    def test_serial_no_to_hex_positive(self):
        serial_no = 1234567890123456789
        # 1234567890123456789 in hex is 112210f47de98115
        expected_hex = "112210f47de98115"
        assert serial_no_to_hex(serial_no) == expected_hex

    def test_serial_no_to_hex_zero(self):
        serial_no = 0
        expected_hex = "0000000000000000"
        assert serial_no_to_hex(serial_no) == expected_hex

    def test_serial_no_to_hex_negative(self):
        serial_no = -1
        expected_hex = "ffffffffffffffff"  # 8-byte two's complement
        assert serial_no_to_hex(serial_no) == expected_hex

    def test_serial_no_to_hex_max_positive_signed_8_byte(self):
        serial_no = (2 ** (8 * 8 - 1)) - 1  # Max positive for signed 8-byte
        expected_hex = "7fffffffffffffff"
        assert serial_no_to_hex(serial_no) == expected_hex

    def test_serial_no_to_hex_min_negative_signed_8_byte(self):
        serial_no = -(2 ** (8 * 8 - 1))  # Min negative for signed 8-byte
        expected_hex = "8000000000000000"
        assert serial_no_to_hex(serial_no) == expected_hex

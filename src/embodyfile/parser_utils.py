"""Parser utilities for parsing."""

from datetime import datetime
import pytz


TIMEZONE_UTC = pytz.timezone("UTC")
TIMEZONE_OSLO = pytz.timezone("Europe/Oslo")


def time_str(time_in_millis: int, version: tuple | None) -> str:
    """Convert time in milliseconds to a formatted string."""
    try:
        timezone = TIMEZONE_UTC
        if version and version <= (5, 3, 9):
            timezone = TIMEZONE_OSLO
        return datetime.fromtimestamp(time_in_millis / 1000, tz=timezone).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    except Exception:
        return "????-??-??T??:??:??.???"


def serial_no_to_hex(serial_no: int) -> str:
    """Convert device serial number to hex string."""
    try:
        return serial_no.to_bytes(8, "big", signed=True).hex()
    except Exception:
        return "unknown"

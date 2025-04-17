"""Data models for the embodyfile package."""

from dataclasses import dataclass
from typing import TypeVar

from embodycodec import file_codec


ProtocolMessageOrChildren = TypeVar("ProtocolMessageOrChildren", bound=file_codec.ProtocolMessage)
PM = TypeVar("PM")


class ProtocolMessageDict(dict):
    """A dictionary with ProtocolMessage sub class as key, and same Protocol Message sub class in list of tuples."""

    def __getitem__(self, k: type[PM]) -> list[tuple[int, PM]]:
        return super().__getitem__(k)


@dataclass
class DeviceInfo:
    """Container for header info."""

    serial: str
    fw_version: str
    timestamp: int


@dataclass
class Data:
    """Container for most important data types collected."""

    device_info: DeviceInfo
    sensor: list[tuple[int, file_codec.ProtocolMessage]]
    afe: list[tuple[int, file_codec.ProtocolMessage]]
    acc: list[tuple[int, file_codec.AccRaw]]
    gyro: list[tuple[int, file_codec.GyroRaw]]
    multi_ecg_ppg_data: list[tuple[int, file_codec.PulseRawList]]
    block_data_ecg: list[tuple[int, file_codec.PulseBlockEcg]]
    block_data_ppg: list[tuple[int, file_codec.PulseBlockPpg]]
    temp: list[tuple[int, file_codec.Temperature]]
    hr: list[tuple[int, file_codec.HeartRate]]
    batt_diag: list[tuple[int, file_codec.BatteryDiagnostics]]

"""Embody file module to parse binary embody files to HDF, CSV or other output formats."""

import csv
import logging
import sys
from dataclasses import asdict
from dataclasses import astuple
from dataclasses import dataclass
from dataclasses import fields
from datetime import datetime
from functools import reduce
from io import BufferedReader
from operator import itemgetter
from pathlib import Path
from typing import Optional
from typing import TypeVar

import pandas as pd
import pytz
from embodycodec import file_codec


TIMEZONE_UTC = pytz.timezone("UTC")
TIMEZONE_OSLO = pytz.timezone("Europe/Oslo")

MIN_TIMESTAMP = datetime(1999, 10, 1, 0, 0).timestamp() * 1000
MAX_TIMESTAMP = datetime(2036, 10, 1, 0, 0).timestamp() * 1000

ProtocolMessageOrChildren = TypeVar(
    "ProtocolMessageOrChildren", bound=file_codec.ProtocolMessage
)
PM = TypeVar("PM")


class ProtocolMessageDict(dict):
    """A dictionary with ProtocolMessage sub class as key, and same Protocol Message sub class in list of tuples."""

    def __getitem__(self, k: type[PM]) -> list[tuple[int, PM]]:
        return super().__getitem__(k)


@dataclass
class DeviceInfo:
    """Contaner for header info."""

    serial: str
    fw_version: str


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


def __write_data(
    fname: Path, data: list[tuple[int, ProtocolMessageOrChildren]]
) -> None:
    if not data:
        return

    logging.info(f"Writing to: {fname}")
    sorted_data = sorted(data, key=itemgetter(0))
    _, header = sorted_data[0]
    version: Optional[tuple] = None
    if isinstance(header, file_codec.Header):
        version = tuple(header.firmware_version)
    columns = ["timestamp"] + [f.name for f in fields(sorted_data[0][1])]
    column_data = [(__time_str(ts, version), *astuple(d)) for ts, d in sorted_data]
    with open(fname, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(column_data)

    logging.info(f"Wrote to: {fname}")


def _to_pandas(data: list[tuple[int, ProtocolMessageOrChildren]]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()

    columns = ["timestamp"] + [f.name for f in fields(data[0][1])]
    column_data = [(ts, *astuple(d)) for ts, d in data]

    df = pd.DataFrame(column_data, columns=columns)
    df.set_index("timestamp", inplace=True)
    df.index = pd.to_datetime(df.index, unit="ms").tz_localize(pytz.utc)
    df = df[~df.index.duplicated()]
    df.sort_index(inplace=True)
    df = df[df[df.columns] < sys.maxsize].dropna()  # remove badly converted values
    return df


def _multi_data2pandas(data: list[tuple[int, file_codec.PulseRawList]]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()

    num_ecg = data[0][1].no_of_ecgs
    num_ppg = data[0][1].no_of_ppgs

    columns = (
        ["timestamp"]
        + [f"ecg_{i}" for i in range(num_ecg)]
        + [f"ppg_{i}" for i in range(num_ppg)]
    )

    column_data = [(ts,) + tuple(d.ecgs) + tuple(d.ppgs) for ts, d in data]

    df = pd.DataFrame(column_data, columns=columns)
    df.set_index("timestamp", inplace=True)
    df.index = pd.to_datetime(df.index, unit="ms").tz_localize(pytz.utc)
    df = df[~df.index.duplicated()]
    df.sort_index(inplace=True)
    return df


def read_data(f: BufferedReader, fail_on_errors=False) -> Data:
    """Parse data from file into memory. Throws LookupError if no Header is found."""
    collections = __read_data_in_memory(f, fail_on_errors)

    multi_ecg_ppg_data: list[tuple[int, file_codec.PulseRawList]] = collections.get(
        file_codec.PulseRawList, []
    )

    block_data_ecg: list[tuple[int, file_codec.PulseBlockEcg]] = collections.get(
        file_codec.PulseBlockEcg, []
    )

    block_data_ppg: list[tuple[int, file_codec.PulseBlockPpg]] = collections.get(
        file_codec.PulseBlockPpg, []
    )

    temp: list[tuple[int, file_codec.Temperature]] = collections.get(
        file_codec.Temperature, []
    )

    hr: list[tuple[int, file_codec.HeartRate]] = collections.get(
        file_codec.HeartRate, []
    )

    sensor_data: list[tuple[int, file_codec.ProtocolMessage]] = list()
    if len(collections.get(file_codec.PpgRaw, [])) > 0:
        sensor_data += collections.get(file_codec.PpgRaw, [])

    ppg_raw_all_list = collections.get(file_codec.PpgRawAll, [])
    if len(ppg_raw_all_list) >= 0:
        sensor_data += [
            (t, file_codec.PpgRaw(d.ecg, d.ppg)) for t, d in ppg_raw_all_list
        ]

    afe_settings: list[tuple[int, file_codec.ProtocolMessage]] = collections.get(
        file_codec.AfeSettings, []
    )
    if len(afe_settings) == 0:
        afe_settings = collections.get(file_codec.AfeSettingsOld, [])
    if len(afe_settings) == 0:
        afe_settings = collections.get(file_codec.AfeSettingsAll, [])

    imu_data: list[tuple[int, file_codec.ImuRaw]] = collections.get(
        file_codec.ImuRaw, []
    )
    if imu_data:
        acc_data = [
            (t, file_codec.AccRaw(d.acc_x, d.acc_y, d.acc_z)) for t, d in imu_data
        ]
        gyro_data = [
            (t, file_codec.GyroRaw(d.gyr_x, d.gyr_y, d.gyr_z)) for t, d in imu_data
        ]
    else:
        acc_data = collections.get(file_codec.AccRaw, [])
        gyro_data = collections.get(file_codec.GyroRaw, [])

    battery_diagnostics: list[
        tuple[int, file_codec.BatteryDiagnostics]
    ] = collections.get(file_codec.BatteryDiagnostics, [])

    if not collections.get(file_codec.Header):
        raise LookupError("Missing header in input file")

    header = collections[file_codec.Header][0][1]

    serial = hex(header.serial)[2:].upper()
    fw_version = ".".join(map(str, tuple(header.firmware_version)))
    logging.info(
        f"Parsed {len(sensor_data)} sensor data, {len(afe_settings)} afe_settings, "
        f"{len(acc_data)} acc_data, {len(gyro_data)} gyro_data, "
        f"{len(multi_ecg_ppg_data)} multi_ecg_ppg_data, "
        f"{len(block_data_ecg)} block_data_ecg, "
        f"{len(block_data_ppg)} block_data_ppg"
    )
    return Data(
        DeviceInfo(serial, fw_version),
        sensor_data,
        afe_settings,
        acc_data,
        gyro_data,
        multi_ecg_ppg_data,
        block_data_ecg,
        block_data_ppg,
        temp,
        hr,
        battery_diagnostics,
    )


def __read_data_in_memory(
    f: BufferedReader, fail_on_errors=False
) -> ProtocolMessageDict:
    """Parse data from file/buffer into RAM."""
    current_off_dac = 0  # Add this to the ppg value
    start_timestamp = 0
    last_full_timestamp = 0  # the last full timestamp we received in the header message or current time message
    current_timestamp = 0  # incremented for every message, either full timestamp or two least significant bytes
    prev_timestamp = 0
    unknown_msgs = 0
    too_old_msgs = 0
    back_leap_msgs = 0
    out_of_seq_msgs = 0
    total_messages = 0
    chunks_read = 0
    lsb_wrap_counter = 0
    pos = 0
    chunk = b""
    collections = ProtocolMessageDict()
    version = None
    prev_msg: Optional[file_codec.ProtocolMessage] = None
    header_found = False

    while True:
        if pos < len(chunk):
            chunk = chunk[pos:]
        else:
            chunk = b""
        new_chunk = f.read(1024)
        if not new_chunk:
            break
        chunks_read += 1
        chunk += new_chunk
        size = len(chunk)
        total_pos = 1024 * chunks_read - size
        pos = 0

        while pos < size:
            start_pos_of_current_msg = total_pos + pos
            message_type = chunk[pos]
            try:
                msg = file_codec.decode_message(chunk[pos:], version)
            except BufferError:  # Not enough bytes available - break to fill buffer
                break
            except LookupError as e:
                err_msg = (
                    f"{start_pos_of_current_msg}: Unknown message type: {hex(message_type)} "
                    f"after {total_messages} messages ({e}). Prev. message: {prev_msg}, pos: {pos},"
                    f" prev buff: {chunk[(pos-22 if pos >= 22 else 0):pos-1].hex()}"
                )
                if fail_on_errors:
                    raise LookupError(err_msg) from None
                logging.warning(err_msg)
                unknown_msgs += 1
                pos += 1
                continue
            pos += 1
            msg_len = msg.length(version)
            logging.debug(f"Pos {pos-1}-{pos-1+msg_len}: New message parsed: {msg}")

            if isinstance(msg, file_codec.Header):
                header = msg
                header_found = True
                version = tuple(header.firmware_version)
                serial = _serial_no_to_hex(header.serial)
                if MAX_TIMESTAMP < header.current_time:
                    err_msg = (
                        f"{start_pos_of_current_msg}: Received full timestamp "
                        f"({header.current_time}/{__time_str(header.current_time, version)}) is"
                        f" greater than max({MAX_TIMESTAMP})"
                    )
                    if fail_on_errors:
                        raise LookupError(err_msg)
                    logging.warning(err_msg)
                else:
                    last_full_timestamp = header.current_time
                    current_timestamp = header.current_time
                    start_timestamp = current_timestamp
                    lsb_wrap_counter = 0
                logging.info(
                    f"{start_pos_of_current_msg}: Found header with serial: "
                    f"{header.serial}/{serial}, "
                    f"fw.v: {version}, current time: "
                    f"{header.current_time}/{__time_str(header.current_time, version)}"
                )
                pos += msg_len
                __add_msg_to_collections(current_timestamp, msg, collections)
                continue
            elif not header_found:
                pos += msg_len
                logging.info(
                    f"{start_pos_of_current_msg}: Skipping msg before header: {msg}"
                )
                continue
            elif isinstance(msg, file_codec.Timestamp):
                timestamp = msg
                current_time = timestamp.current_time
                if MAX_TIMESTAMP < current_time:
                    err_msg = (
                        f"{start_pos_of_current_msg}: Received full timestamp "
                        f"({current_time}/{__time_str(current_time, version)}) is greater than "
                        f"max({MAX_TIMESTAMP}). Skipping"
                    )
                    if fail_on_errors:
                        raise LookupError(err_msg)
                    logging.warn(err_msg)
                elif current_time < last_full_timestamp:
                    err_msg = (
                        f"{start_pos_of_current_msg}: Received full timestamp "
                        f"({current_time}/{__time_str(current_time, version)}) is less "
                        f"than last_full_timestamp ({last_full_timestamp}/{__time_str(last_full_timestamp, version)})"
                    )
                    if fail_on_errors:
                        raise LookupError(err_msg)
                    logging.warn(err_msg)
                else:
                    last_full_timestamp = current_time
                    current_timestamp = current_time
                    lsb_wrap_counter = 0
                pos += msg_len
                __add_msg_to_collections(current_timestamp, msg, collections)
                continue
            elif isinstance(msg, file_codec.PulseBlockEcg) or isinstance(
                msg, file_codec.PulseBlockPpg
            ):
                pos += msg_len
                total_messages += 1
                prev_msg = msg
                __add_msg_to_collections(msg.time, msg, collections)
                continue

            if current_timestamp < MIN_TIMESTAMP:
                too_old_msgs += 1
                err_msg = (
                    f"{start_pos_of_current_msg}: Timestamp is too old "
                    f"({current_timestamp}/{__time_str(current_timestamp, version)}). Still adding message"
                )
                if fail_on_errors:
                    raise LookupError(err_msg)
                logging.warning(err_msg)

            # all other message types start with a time tick - two least significant bytes of epoch timestamp
            two_lsb_of_timestamp = (
                msg.two_lsb_of_timestamp
                if isinstance(msg, file_codec.TimetickedMessage)
                and msg.two_lsb_of_timestamp
                else 0
            )

            # apply the two least significant bytes to the current timestamp
            original_two_lsbs = current_timestamp & 0xFFFF
            if original_two_lsbs > 65000 and two_lsb_of_timestamp < 100:
                current_timestamp += 0x10000  # wrapped counter, incr byte 3 (first after two least sign. bytes)
                lsb_wrap_counter += 1
            elif two_lsb_of_timestamp > 65000 and original_two_lsbs < 100:
                # corner case - we've received an older, pre-wrapped message
                current_timestamp -= 0x10000
                lsb_wrap_counter -= 1

            current_timestamp = current_timestamp >> 16 << 16 | two_lsb_of_timestamp

            if isinstance(msg, file_codec.PpgRaw):
                if version and version >= (4, 0, 1):
                    msg.ppg += current_off_dac  # add offset to ppg value
                    msg.ppg = -msg.ppg  # Invert
            elif isinstance(msg, file_codec.PpgRawAll):
                if version and version >= (4, 0, 1):
                    msg.ppg += current_off_dac  # add offset to ppg value
                    msg.ppg = -msg.ppg  # Invert
                    msg.ppg_red += current_off_dac  # add offset to ppg value
                    msg.ppg_red = -msg.ppg_red  # Invert
                    msg.ppg_ir += current_off_dac  # add offset to ppg value
                    msg.ppg_ir = -msg.ppg_ir  # Invert
            elif isinstance(msg, file_codec.PulseRawList):
                if msg.ppgs and len(msg.ppgs) > 0:
                    for i in range(0, len(msg.ppgs)):
                        msg.ppgs[i] = -msg.ppgs[i]  # Invert
            elif isinstance(msg, file_codec.AfeSettings):
                afe = msg
                current_off_dac = int(-afe.off_dac * afe.relative_gain)
                current_iled = afe.led1 + afe.led4
                logging.debug(
                    f"Message {total_messages} new AFE: {msg}, iLED={current_iled} "
                    f"timestamp={__time_str(current_timestamp, version)}"
                )

            if prev_timestamp > 0 and current_timestamp > prev_timestamp + 1000:
                jump = current_timestamp - prev_timestamp
                err_msg = (
                    f"Jump > 1 sec - Message #{total_messages+1} "
                    f"timestamp={current_timestamp}/{__time_str(current_timestamp, version)} "
                    f"Previous message timestamp={prev_timestamp}/{__time_str(prev_timestamp, version)} "
                    f"jump={jump}ms 2lsbs={msg.two_lsb_of_timestamp if isinstance(msg, file_codec.TimetickedMessage) else 0}"
                )
                logging.info(err_msg)
                if fail_on_errors:
                    raise LookupError(err_msg) from None
            prev_timestamp = current_timestamp
            prev_msg = msg
            pos += msg_len
            total_messages += 1

            __add_msg_to_collections(current_timestamp, msg, collections)

    logging.info("Parsing complete. Summary of messages parsed:")
    for key in collections:
        msg_list = collections[key]
        total_length = reduce(lambda x, y: x + y[1].length(), msg_list, 0)
        logging.info(
            f"{key.__name__} count: {len(msg_list)}, size: {total_length} bytes"
        )
        __analyze_timestamps(msg_list)
    logging.info(
        f"Parsed {total_messages} messages in time range {__time_str(start_timestamp, version)} "
        f"to {__time_str(current_timestamp, version)}, "
        f"with {unknown_msgs} unknown, {too_old_msgs} too old, {back_leap_msgs} backward leaps (>100 ms backwards), "
        f"{out_of_seq_msgs} out of sequence"
    )

    if collections.get(file_codec.PulseBlockEcg) or collections.get(
        file_codec.PulseBlockPpg
    ):
        __convert_block_messages_to_pulse_list(collections)

    return collections


def __convert_block_messages_to_pulse_list(collections: ProtocolMessageDict) -> None:
    """Converts ecg and ppg block messages to pulse list messages."""
    ecg_messages: Optional[
        list[tuple[int, file_codec.PulseBlockEcg]]
    ] = collections.get(file_codec.PulseBlockEcg)
    ppg_messages: Optional[
        list[tuple[int, file_codec.PulseBlockPpg]]
    ] = collections.get(file_codec.PulseBlockPpg)

    assert ecg_messages is not None
    assert ppg_messages is not None
    dup_ecg_timestamps = 0
    dup_ppg_timestamps = 0
    merged_data: dict[int, file_codec.PulseRawList] = {}

    for _, ecg_block in ecg_messages:
        timestamp = ecg_block.time
        no_of_ecgs = ecg_block.channel + 1
        for ecg_sample in ecg_block.samples:
            if timestamp not in merged_data:
                merged_data[timestamp] = file_codec.PulseRawList(
                    format=0,
                    no_of_ecgs=no_of_ecgs,
                    no_of_ppgs=0,
                    ecgs=([0] * no_of_ecgs),
                    ppgs=[],
                )
                merged_data[timestamp].ecgs[no_of_ecgs - 1] = ecg_sample
            else:
                if merged_data[timestamp].no_of_ecgs == no_of_ecgs:  # same channel
                    dup_ecg_timestamps += 1
                    logging.debug(
                        f"Ecg sample in block with duplicate timestamp "
                        f"{timestamp}. Total samples in block: {len(ecg_block.samples)}. Not adjusting."
                    )
                elif merged_data[timestamp].no_of_ecgs < no_of_ecgs:
                    merged_data[timestamp].ecgs.extend(
                        [0] * (no_of_ecgs - merged_data[timestamp].no_of_ecgs)
                    )
                    merged_data[timestamp].no_of_ecgs = no_of_ecgs
                merged_data[timestamp].ecgs[no_of_ecgs - 1] = ecg_sample
            timestamp += 1

    for _, ppg_block in ppg_messages:
        timestamp = ppg_block.time
        no_of_ppgs = ppg_block.channel + 1
        for ppg_sample in ppg_block.samples:
            if timestamp not in merged_data:
                merged_data[timestamp] = file_codec.PulseRawList(
                    format=0,
                    no_of_ecgs=0,
                    no_of_ppgs=no_of_ppgs,
                    ecgs=[],
                    ppgs=([0] * no_of_ppgs),
                )
                merged_data[timestamp].ppgs[no_of_ppgs - 1] = -ppg_sample
            else:
                if merged_data[timestamp].no_of_ppgs == no_of_ppgs:  # same channel
                    dup_ppg_timestamps += 1
                    logging.debug(
                        f"Ppg sample in block with duplicate timestamp "
                        f"{timestamp}. Total samples in block: {len(ppg_block.samples)} Not adjusting."
                    )
                elif merged_data[timestamp].no_of_ppgs < no_of_ppgs:
                    merged_data[timestamp].ppgs.extend(
                        [0] * (no_of_ppgs - merged_data[timestamp].no_of_ppgs)
                    )
                    merged_data[timestamp].no_of_ppgs = no_of_ppgs
                merged_data[timestamp].ppgs[no_of_ppgs - 1] = -ppg_sample
            timestamp += 1
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(
            f"Converted {sum([len(block.samples) for _,block in ecg_messages])} ecg blocks "
            f" {sum([len(block.samples) for _,block in ppg_messages])} ppg blocks "
            f" to {len(merged_data)} pulse list messages"
        )
    if dup_ecg_timestamps > 0 or dup_ppg_timestamps > 0:
        logging.warning(
            f"Duplicate timestamps in ecg blocks: {dup_ecg_timestamps}, ppg blocks: {dup_ppg_timestamps}"
        )

    collections[file_codec.PulseRawList] = [
        (timestamp, pulse_raw_list) for timestamp, pulse_raw_list in merged_data.items()
    ]
    collections[file_codec.PulseBlockPpg] = []
    collections[file_codec.PulseBlockEcg] = []


def _serial_no_to_hex(serial_no: int) -> str:
    try:
        return serial_no.to_bytes(8, "big", signed=True).hex()
    except Exception:
        return "unknown"


def __add_msg_to_collections(
    current_timestamp: int,
    msg: file_codec.ProtocolMessage,
    collections: ProtocolMessageDict,
) -> None:
    if collections.get(msg.__class__) is None:
        collections[msg.__class__] = []
    collections[msg.__class__] += [(current_timestamp, msg)]


def data2csv(data: Data, fname: Path) -> None:
    __write_data(__fname_with_suffix(fname, "afe"), data.afe)
    __write_data(__fname_with_suffix(fname, "acc"), data.acc)
    __write_data(__fname_with_suffix(fname, "gyro"), data.gyro)
    __write_data(__fname_with_suffix(fname, "multi"), data.multi_ecg_ppg_data)
    __write_data(__fname_with_suffix(fname, "temp"), data.temp)
    __write_data(__fname_with_suffix(fname, "hr"), data.hr)
    __write_data(__fname_with_suffix(fname, "battdiag"), data.batt_diag)
    __write_data(fname, data.sensor)


def data2hdf(data: Data, fname: Path) -> None:
    logging.info(f"Converting data to HDF: {fname}")
    df_multidata = _multi_data2pandas(data.multi_ecg_ppg_data)
    df_data = _to_pandas(data.sensor)
    df_afe = _to_pandas(data.afe)
    df_temp = _to_pandas(data.temp)
    df_hr = _to_pandas(data.hr)

    if not data.acc or not data.gyro:
        logging.warning(f"No IMU data: {fname}")
        df_imu = pd.DataFrame()
    else:
        df_imu = pd.merge_asof(
            _to_pandas(data.acc),
            _to_pandas(data.gyro),
            left_index=True,
            right_index=True,
            tolerance=pd.Timedelta("2ms"),
            direction="nearest",
        )

    df_data.to_hdf(fname, "data", mode="w")
    df_multidata.to_hdf(fname, "multidata", mode="a")
    df_imu.to_hdf(fname, "imu", mode="a")
    df_afe.to_hdf(fname, "afe", mode="a")
    df_temp.to_hdf(fname, "temp", mode="a")
    df_hr.to_hdf(fname, "hr", mode="a")

    info = {k: [v] for k, v in asdict(data.device_info).items()}
    pd.DataFrame(info).to_hdf(fname, "device_info", mode="a")

    logging.info(f"Converted data to HDF: {fname}")


def __analyze_timestamps(data: list[tuple[int, ProtocolMessageOrChildren]]) -> None:
    ts: list[int] = [x[0] for x in data]
    num_duplicates = len(ts) - len(set(ts))
    diff = [x - y for x, y in zip(ts[1:], ts)]
    num_big_leaps = len([x for x in diff if x > 20])
    num_small_leaps = len([x for x in diff if 4 < x <= 20])
    logging.debug(f"Found {num_big_leaps} big time leaps (>20ms)")
    logging.debug(f"Found {num_small_leaps} small time leaps (5-20ms)")
    logging.debug(f"Found {num_duplicates} duplicates")


def __fname_with_suffix(dst_fname: Path, suffix: str) -> Path:
    return dst_fname.with_stem(dst_fname.stem + "_" + suffix)


def __time_str(time_in_millis: int, version: Optional[tuple]) -> str:
    try:
        timezone = TIMEZONE_UTC
        if version and version <= (5, 3, 9):
            timezone = TIMEZONE_OSLO
        return datetime.fromtimestamp(time_in_millis / 1000, tz=timezone).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3]
    except Exception:
        return "????-??-??T??:??:??.???"

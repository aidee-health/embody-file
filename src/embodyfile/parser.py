"""Parser module for embodyfile package."""

import logging
from datetime import datetime
from functools import reduce
from io import BufferedReader

import pytz
from embodycodec import file_codec

from .models import Data
from .models import DeviceInfo
from .models import ProtocolMessageDict


# Constants
TIMEZONE_UTC = pytz.timezone("UTC")
TIMEZONE_OSLO = pytz.timezone("Europe/Oslo")
MIN_TIMESTAMP = datetime(1999, 10, 1, 0, 0).timestamp() * 1000
MAX_TIMESTAMP = datetime(2036, 10, 1, 0, 0).timestamp() * 1000


def read_data(f: BufferedReader, fail_on_errors=False, samplerate=1000.0) -> Data:
    """Parse data from file into memory. Throws LookupError if no Header is found."""
    collections = _read_data_in_memory(f, fail_on_errors, samplerate=samplerate)

    multi_ecg_ppg_data: list[tuple[int, file_codec.PulseRawList]] = collections.get(file_codec.PulseRawList, [])

    block_data_ecg: list[tuple[int, file_codec.PulseBlockEcg]] = collections.get(file_codec.PulseBlockEcg, [])

    block_data_ppg: list[tuple[int, file_codec.PulseBlockPpg]] = collections.get(file_codec.PulseBlockPpg, [])

    temp: list[tuple[int, file_codec.Temperature]] = collections.get(file_codec.Temperature, [])

    hr: list[tuple[int, file_codec.HeartRate]] = collections.get(file_codec.HeartRate, [])

    sensor_data: list[tuple[int, file_codec.ProtocolMessage]] = []
    if len(collections.get(file_codec.PpgRaw, [])) > 0:
        sensor_data += collections.get(file_codec.PpgRaw, [])

    ppg_raw_all_list = collections.get(file_codec.PpgRawAll, [])
    if len(ppg_raw_all_list) >= 0:
        sensor_data += [(t, file_codec.PpgRaw(d.ecg, d.ppg)) for t, d in ppg_raw_all_list]

    afe_settings: list[tuple[int, file_codec.ProtocolMessage]] = collections.get(file_codec.AfeSettings, [])
    if len(afe_settings) == 0:
        afe_settings = collections.get(file_codec.AfeSettingsOld, [])
    if len(afe_settings) == 0:
        afe_settings = collections.get(file_codec.AfeSettingsAll, [])

    imu_data: list[tuple[int, file_codec.ImuRaw]] = collections.get(file_codec.ImuRaw, [])
    if imu_data:
        acc_data = [(t, file_codec.AccRaw(d.acc_x, d.acc_y, d.acc_z)) for t, d in imu_data]
        gyro_data = [(t, file_codec.GyroRaw(d.gyr_x, d.gyr_y, d.gyr_z)) for t, d in imu_data]
    else:
        acc_data = collections.get(file_codec.AccRaw, [])
        gyro_data = collections.get(file_codec.GyroRaw, [])

    battery_diagnostics: list[tuple[int, file_codec.BatteryDiagnostics]] = collections.get(
        file_codec.BatteryDiagnostics, []
    )

    if not collections.get(file_codec.Header):
        raise LookupError("Missing header in input file")

    header = collections[file_codec.Header][0][1]

    serial = _serial_no_to_hex(header.serial)
    fw_version = ".".join(map(str, tuple(header.firmware_version)))
    logging.info(
        f"Parsed {len(sensor_data)} sensor data, {len(afe_settings)} afe_settings, "
        f"{len(acc_data)} acc_data, {len(gyro_data)} gyro_data, "
        f"{len(multi_ecg_ppg_data)} multi_ecg_ppg_data, "
        f"{len(block_data_ecg)} block_data_ecg, "
        f"{len(block_data_ppg)} block_data_ppg"
    )
    return Data(
        DeviceInfo(serial, fw_version, header.current_time),
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


def _read_data_in_memory(f: BufferedReader, fail_on_errors=False, samplerate=1000.0) -> ProtocolMessageDict:
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
    max_ecg_channels = 0
    max_ppg_channels = 0
    pos = 0
    # Use bytearray instead of bytes for better performance with concatenation
    chunk = bytearray()
    collections = ProtocolMessageDict()
    version: tuple[int, int, int] | None = None
    prev_msg: file_codec.ProtocolMessage | None = None
    header_found = False

    buffer_size = 16384  # 16KB buffer for optimal read performance
    total_pos = 0

    while True:
        if pos > 0:
            if pos < len(chunk):
                # Move remaining data to the beginning of the buffer
                chunk = chunk[pos:]
            else:
                chunk = bytearray()

        new_chunk = f.read(buffer_size)
        if not new_chunk:
            break

        chunks_read += 1
        chunk.extend(new_chunk)
        size = len(chunk)
        total_pos += pos
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
                    f" prev buff: {chunk[(pos - 22 if pos >= 22 else 0) : pos - 1].hex()}"
                )
                if fail_on_errors:
                    raise LookupError(err_msg) from None
                if logging.getLogger().isEnabledFor(logging.WARNING):
                    logging.warning(err_msg)
                unknown_msgs += 1
                pos += 1
                continue
            pos += 1
            msg_len = msg.length(version)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                if isinstance(msg, file_codec.TimetickedMessage):
                    logging.debug(
                        f"Pos {pos - 1}-{pos - 1 + msg_len}: New message with tt={msg.two_lsb_of_timestamp} parsed: {msg}"
                    )
                elif hasattr(msg, "current_time"):
                    logging.debug(
                        f"Pos {pos - 1}-{pos - 1 + msg_len}: New message with ts={msg.current_time} parsed: {msg}"
                    )
                elif hasattr(msg, "time"):
                    logging.debug(f"Pos {pos - 1}-{pos - 1 + msg_len}: New message with ts={msg.time} parsed: {msg}")
                else:
                    logging.debug(f"Pos {pos - 1}-{pos - 1 + msg_len}: New message parsed: {msg}")

            if isinstance(msg, file_codec.Header):
                header = msg
                header_found = True
                version = (
                    header.firmware_version[0],
                    header.firmware_version[1],
                    header.firmware_version[2],
                )
                serial = _serial_no_to_hex(header.serial)
                if MAX_TIMESTAMP < header.current_time:
                    err_msg = (
                        f"{start_pos_of_current_msg}: Received full timestamp "
                        f"({header.current_time}/{_time_str(header.current_time, version)}) is"
                        f" greater than max({MAX_TIMESTAMP})"
                    )
                    if fail_on_errors:
                        raise LookupError(err_msg)
                    if logging.getLogger().isEnabledFor(logging.WARNING):
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
                    f"{header.current_time}/{_time_str(header.current_time, version)}"
                )
                pos += msg_len
                _add_msg_to_collections(current_timestamp, msg, collections)
                continue
            elif not header_found:
                pos += msg_len
                if logging.getLogger().isEnabledFor(logging.INFO):
                    logging.info(f"{start_pos_of_current_msg}: Skipping msg before header: {msg}")
                continue
            elif isinstance(msg, file_codec.Timestamp):
                timestamp = msg
                current_time = timestamp.current_time
                if MAX_TIMESTAMP < current_time:
                    err_msg = (
                        f"{start_pos_of_current_msg}: Received full timestamp "
                        f"({current_time}/{_time_str(current_time, version)}) is greater than "
                        f"max({MAX_TIMESTAMP}). Skipping"
                    )
                    if fail_on_errors:
                        raise LookupError(err_msg)
                    if logging.getLogger().isEnabledFor(logging.WARNING):
                        logging.warning(err_msg)
                elif current_time < last_full_timestamp:
                    err_msg = (
                        f"{start_pos_of_current_msg}: Received full timestamp "
                        f"({current_time}/{_time_str(current_time, version)}) is less "
                        f"than last_full_timestamp ({last_full_timestamp}/{_time_str(last_full_timestamp, version)})"
                    )
                    if fail_on_errors:
                        raise LookupError(err_msg)
                    if logging.getLogger().isEnabledFor(logging.WARNING):
                        logging.warning(err_msg)
                else:
                    last_full_timestamp = current_time
                    current_timestamp = current_time
                    lsb_wrap_counter = 0
                pos += msg_len
                _add_msg_to_collections(current_timestamp, msg, collections)
                continue
            elif isinstance(msg, file_codec.PulseBlockEcg) or isinstance(msg, file_codec.PulseBlockPpg):
                pos += msg_len
                total_messages += 1
                prev_msg = msg
                if isinstance(msg, file_codec.PulseBlockPpg):  # Count here to reduce traversing later
                    max_ppg_channels = max(max_ppg_channels, msg.channel)
                else:
                    max_ecg_channels = max(max_ecg_channels, msg.channel)
                _add_msg_to_collections(msg.time, msg, collections)
                continue

            if current_timestamp < MIN_TIMESTAMP:
                too_old_msgs += 1
                err_msg = (
                    f"{start_pos_of_current_msg}: Timestamp is too old "
                    f"({current_timestamp}/{_time_str(current_timestamp, version)}). Still adding message"
                )
                if fail_on_errors:
                    raise LookupError(err_msg)
                if logging.getLogger().isEnabledFor(logging.WARNING):
                    logging.warning(err_msg)

            # all other message types start with a time tick - two least significant bytes of epoch timestamp
            two_lsb_of_timestamp = (
                msg.two_lsb_of_timestamp
                if isinstance(msg, file_codec.TimetickedMessage) and msg.two_lsb_of_timestamp
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

            # Pre-compute this once for all message handlers
            should_adjust_ppg = version and version >= (4, 0, 1)

            # PPG Raw messages - handle PPG inversion and offset
            if isinstance(msg, file_codec.PpgRaw):
                if should_adjust_ppg:
                    # Combine addition and inversion into one operation
                    msg.ppg = -(msg.ppg + current_off_dac)

            # PPG Raw All messages - handle PPG inversion and offset for all channels
            elif isinstance(msg, file_codec.PpgRawAll):
                if should_adjust_ppg:
                    # Combine addition and inversion into one operation for all channels
                    msg.ppg = -(msg.ppg + current_off_dac)
                    msg.ppg_red = -(msg.ppg_red + current_off_dac)
                    msg.ppg_ir = -(msg.ppg_ir + current_off_dac)

            # Pulse Raw List messages - invert all PPG values using list comprehension
            elif isinstance(msg, file_codec.PulseRawList):
                if msg.ppgs and len(msg.ppgs) > 0:
                    msg.ppgs = [-ppg for ppg in msg.ppgs]

            # AFE Settings - update current offset DAC value
            elif isinstance(msg, file_codec.AfeSettings):
                afe = msg
                current_off_dac = int(-afe.off_dac * afe.relative_gain)
                current_iled = afe.led1 + afe.led4
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.debug(
                        f"Message {total_messages} new AFE: {msg}, iLED={current_iled} "
                        f"timestamp={_time_str(current_timestamp, version)}"
                    )

            if prev_timestamp > 0 and current_timestamp > prev_timestamp + 1000:
                jump = current_timestamp - prev_timestamp
                err_msg = (
                    f"Jump > 1 sec - Message #{total_messages + 1} "
                    f"timestamp={current_timestamp}/{_time_str(current_timestamp, version)} "
                    f"Previous message timestamp={prev_timestamp}/{_time_str(prev_timestamp, version)} "
                    f"jump={jump}ms 2lsbs={msg.two_lsb_of_timestamp if isinstance(msg, file_codec.TimetickedMessage) else 0}"
                )
                if logging.getLogger().isEnabledFor(logging.INFO):
                    logging.info(err_msg)
                if fail_on_errors:
                    raise LookupError(err_msg) from None
            prev_timestamp = current_timestamp
            prev_msg = msg
            pos += msg_len
            total_messages += 1

            _add_msg_to_collections(current_timestamp, msg, collections)

    logging.info("Parsing complete. Summary of messages parsed:")
    for key in collections:
        msg_list = collections[key]
        total_length = reduce(lambda x, y: x + y[1].length(), msg_list, 0)
        logging.info(f"{key.__name__} count: {len(msg_list)}, size: {total_length} bytes")
        _analyze_timestamps(msg_list)
    logging.info(
        f"Parsed {total_messages} messages in time range {_time_str(start_timestamp, version)} "
        f"to {_time_str(current_timestamp, version)}, "
        f"with {unknown_msgs} unknown, {too_old_msgs} too old, {back_leap_msgs} backward leaps (>100 ms backwards), "
        f"{out_of_seq_msgs} out of sequence"
    )

    if file_codec.PulseBlockEcg in collections or file_codec.PulseBlockPpg in collections:
        __convert_block_messages_to_pulse_list(
            collections, samplerate=samplerate, max_ecg_channels=max_ecg_channels, max_ppg_channels=max_ppg_channels
        )

    return collections


def __convert_block_messages_to_pulse_list(
    collections: ProtocolMessageDict,
    samplerate: float = 1000.0,
    stamp_tol: float = 0.95,
    stamp_gap_limit: float = 5.0,
    max_ecg_channels: int = 0,
    max_ppg_channels: int = 0,
) -> None:
    """Converts ecg and ppg block messages to pulse list messages."""
    ecg_messages: list[tuple[int, file_codec.PulseBlockEcg]] | None = collections.get(file_codec.PulseBlockEcg)
    ppg_messages: list[tuple[int, file_codec.PulseBlockPpg]] | None = collections.get(file_codec.PulseBlockPpg)
    assert ecg_messages is not None
    assert ppg_messages is not None
    sampleinterval_ms = (
        1000 / samplerate
    )  # Creating a sampling interval that can be scaled relative to number of samples
    merged_data: dict[int, file_codec.PulseRawList] = {}
    max_ecg_channels = 0
    max_ppg_channels = 0
    # Pre-count ecg and ppg channel numbers to figure out max, to be used for all rows of data
    if max_ecg_channels == 0:
        for _, ecg_block in ecg_messages:
            max_ecg_channels = max(ecg_block.channel + 1, max_ecg_channels)
    if max_ppg_channels == 0:
        for _, ppg_block in ppg_messages:
            max_ppg_channels = max(ppg_block.channel + 1, max_ppg_channels)

    locked_initial_ecg_timestamp = [0] * max_ecg_channels
    ecg_sample_counters = [0] * max_ecg_channels
    ecg_block_counters = [0] * max_ecg_channels
    ecg_early_counters = [0] * max_ecg_channels
    ecg_late_counters = [0] * max_ecg_channels
    dup_ecg_timestamps = [0] * max_ecg_channels

    locked_initial_ppg_timestamp = [0] * max_ppg_channels
    ppg_sample_counters = [0] * max_ppg_channels
    ppg_block_counters = [0] * max_ppg_channels
    ppg_early_counters = [0] * max_ppg_channels
    ppg_late_counters = [0] * max_ppg_channels
    dup_ppg_timestamps = [0] * max_ppg_channels

    for _, ecg_block in ecg_messages:
        if locked_initial_ecg_timestamp[ecg_block.channel] == 0:
            locked_initial_ecg_timestamp[ecg_block.channel] = ecg_block.time
        else:  # Check the accuracy/skew of the calculated timestamp vs the block timestamp
            first_samplestamp = (
                locked_initial_ecg_timestamp[ecg_block.channel]
                + ecg_sample_counters[ecg_block.channel] * sampleinterval_ms
            )
            stamp_diff = first_samplestamp - ecg_block.time  # Positive means the blocks timestamps are too early
            if stamp_diff > stamp_tol:
                ecg_early_counters[ecg_block.channel] += 1
            elif stamp_diff < -stamp_tol:
                ecg_late_counters[ecg_block.channel] += 1
                if stamp_diff < -stamp_gap_limit:  # Treat gaps larger than stamp_gap_limit as skips in data
                    locked_initial_ecg_timestamp[ecg_block.channel] = ecg_block.time  # Take new locked time
                    ecg_sample_counters[ecg_block.channel] = 0  # Reset counter
                    if logging.getLogger().isEnabledFor(logging.INFO):
                        logging.info(
                            f"ECG{ecg_block.channel} block {ecg_block_counters[ecg_block.channel]} has late timestamp of {ecg_block.time} but was expecting {first_samplestamp}"
                        )

        for ecg_sample in ecg_block.samples:
            samplestamp = int(
                locked_initial_ecg_timestamp[ecg_block.channel]
                + ecg_sample_counters[ecg_block.channel] * sampleinterval_ms
            )
            if samplestamp not in merged_data:
                merged_data[samplestamp] = file_codec.PulseRawList(
                    format=0,
                    no_of_ecgs=max_ecg_channels,
                    no_of_ppgs=max_ppg_channels,
                    ecgs=[0] * max_ecg_channels,
                    ppgs=[0] * max_ppg_channels,
                )
            elif merged_data[samplestamp].ecgs[ecg_block.channel] is not None:  # Data already entered
                dup_ecg_timestamps[ecg_block.channel] += 1
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.debug(
                        f"ECG{ecg_block.channel} sample {ecg_sample_counters[ecg_block.channel]} from block "
                        f"{ecg_block_counters[ecg_block.channel]} has duplicate timestamp {samplestamp}. Value {merged_data[samplestamp].ecgs[ecg_block.channel]} overwritten by {int(ecg_sample)}."
                    )
            merged_data[samplestamp].ecgs[ecg_block.channel] = int(ecg_sample)
            ecg_sample_counters[ecg_block.channel] += 1  # Count sample
        ecg_block_counters[ecg_block.channel] += 1  # Count block

    for _, ppg_block in ppg_messages:
        if locked_initial_ppg_timestamp[ppg_block.channel] == 0:
            locked_initial_ppg_timestamp[ppg_block.channel] = ppg_block.time
        else:  # Check the accuracy/skew of the calculated timestamp vs the block timestamp
            first_samplestamp = (
                locked_initial_ppg_timestamp[ppg_block.channel]
                + ppg_sample_counters[ppg_block.channel] * sampleinterval_ms
            )
            stamp_diff = first_samplestamp - ppg_block.time  # Positive means the blocks timestamps are too early
            if stamp_diff > stamp_tol:
                ppg_early_counters[ppg_block.channel] += 1
            elif stamp_diff < -stamp_tol:
                ppg_late_counters[ppg_block.channel] += 1
                if stamp_diff < -stamp_gap_limit:  # Treat gaps larger than stamp_gap_limit as skips in data
                    locked_initial_ppg_timestamp[ppg_block.channel] = ppg_block.time  # Take new locked time
                    ppg_sample_counters[ppg_block.channel] = 0  # Reset counter
                    if logging.getLogger().isEnabledFor(logging.INFO):
                        logging.info(
                            f"PPG{ppg_block.channel} block {ppg_late_counters[ppg_block.channel]} has late timestamp of {ppg_block.time} but was expecting {first_samplestamp}"
                        )

        for ppg_sample in ppg_block.samples:
            samplestamp = int(
                locked_initial_ppg_timestamp[ppg_block.channel]
                + ppg_sample_counters[ppg_block.channel] * sampleinterval_ms
            )
            if samplestamp not in merged_data:
                # print(f"{ppg_sample_counters[ppg_block.channel]} {samplestamp} not found")
                merged_data[samplestamp] = file_codec.PulseRawList(
                    format=0,
                    no_of_ecgs=max_ecg_channels,
                    no_of_ppgs=max_ppg_channels,
                    ecgs=[0] * max_ecg_channels,
                    ppgs=[0] * max_ppg_channels,
                )
                merged_data[samplestamp].ppgs[ppg_block.channel] = -int(ppg_sample)
            elif merged_data[samplestamp].ppgs[ppg_block.channel] is not None:  # Data already entered
                dup_ppg_timestamps[ppg_block.channel] += 1
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.debug(
                        f"PPG{ppg_block.channel} sample {ppg_sample_counters[ppg_block.channel]} from block "
                        f"{ppg_block_counters[ppg_block.channel]} has duplicate timestamp {samplestamp}. Value {merged_data[samplestamp].ppgs[ppg_block.channel]} overwritten by {int(ppg_sample)}."
                    )
            merged_data[samplestamp].ppgs[ppg_block.channel] = -int(ppg_sample)
            ppg_sample_counters[ppg_block.channel] += 1  # Count sample
        ppg_block_counters[ppg_block.channel] += 1  # Count block
        # if ppg_block_counters[ppg_block.channel]>500:
        #    break
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(
            f"Converted {sum([len(block.samples) for _, block in ecg_messages])} ecg blocks "
            f" {sum([len(block.samples) for _, block in ppg_messages])} ppg blocks "
            f" to {len(merged_data)} pulse list messages"
        )
    if logging.getLogger().isEnabledFor(logging.INFO):
        for chan in range(max_ecg_channels):
            if dup_ecg_timestamps[chan] > 0:
                logging.info(f"Duplicate timestamp count for ECG{chan}: {dup_ecg_timestamps}")
    if logging.getLogger().isEnabledFor(logging.INFO):
        for chan in range(max_ppg_channels):
            if dup_ppg_timestamps[chan] > 0:
                logging.info(f"Duplicate timestamp count for PPG{chan}: {dup_ppg_timestamps}")

    collections[file_codec.PulseRawList] = list(merged_data.items())

    if logging.getLogger().isEnabledFor(logging.DEBUG):
        for timestamp, prl in collections[file_codec.PulseRawList]:
            if prl.no_of_ppgs < len(ppg_block_counters):
                logging.debug(f"{timestamp} - Missing ppg for entry {prl}")
            if prl.no_of_ecgs < len(ecg_block_counters):
                logging.debug(f"{timestamp} - Missing ecg for entry {prl}")

    if logging.getLogger().isEnabledFor(logging.INFO):
        for n in range(len(ecg_late_counters)):
            if ecg_late_counters[n] > 0:
                logging.info(f"ECG{n} has {ecg_late_counters[n]} blocks with late timestamps.")
            if ecg_early_counters[n] > 0:
                logging.info(f"ECG{n} has {ecg_early_counters[n]} blocks with early timestamps.")
        for n in range(len(ppg_late_counters)):
            if ppg_late_counters[n] > 0:
                logging.info(f"PPG{n} has {ppg_late_counters[n]} blocks with late timestamps.")
            if ppg_early_counters[n] > 0:
                logging.info(f"PPG{n} has {ppg_early_counters[n]} blocks with early timestamps.")
    collections[file_codec.PulseBlockPpg] = []
    collections[file_codec.PulseBlockEcg] = []


def _serial_no_to_hex(serial_no: int) -> str:
    try:
        return serial_no.to_bytes(8, "big", signed=True).hex()
    except Exception:
        return "unknown"


def _add_msg_to_collections(
    current_timestamp: int,
    msg: file_codec.ProtocolMessage,
    collections: ProtocolMessageDict,
) -> None:
    """Add a message to the collections dictionary.

    Efficiently stores the message in the appropriate collection based on its type.

    Args:
        current_timestamp: The timestamp for the message
        msg: The protocol message to store
        collections: Dictionary of message collections by type
    """
    msg_class = msg.__class__

    # Use dict.setdefault() to ensure the list exists in a single operation
    # and retrieve the existing list in one dictionary access
    collections.setdefault(msg_class, []).append((current_timestamp, msg))


def _analyze_timestamps(data: list[tuple[int, file_codec.ProtocolMessage]]) -> None:
    """Analyze timestamp patterns in the data.

    This function efficiently analyzes timestamp sequences to detect:
    - Duplicates: Multiple messages with identical timestamps
    - Big time leaps: Jumps of more than 20ms between consecutive messages
    - Small time leaps: Jumps between 5-20ms between consecutive messages

    Args:
        data: List of timestamp and message tuples
    """
    # Only process if debug logging is enabled to avoid unnecessary processing
    if not logging.getLogger().isEnabledFor(logging.DEBUG):
        return

    # Extract timestamps once and store in a tuple for better performance
    ts = tuple(x[0] for x in data)

    if not ts:  # Handle empty data case
        return

    # Calculate duplicates efficiently using sets
    unique_ts = set(ts)
    num_duplicates = len(ts) - len(unique_ts)

    # Calculate time differences in a single pass if we have at least 2 timestamps
    num_big_leaps = 0
    num_small_leaps = 0

    if len(ts) > 1:
        # Use a generator expression with enumerate to avoid creating additional lists
        for i in range(1, len(ts)):
            diff = ts[i] - ts[i - 1]
            if diff > 20:
                num_big_leaps += 1
            elif 4 < diff <= 20:
                num_small_leaps += 1

    logging.debug(f"Found {num_big_leaps} big time leaps (>20ms)")
    logging.debug(f"Found {num_small_leaps} small time leaps (5-20ms)")
    logging.debug(f"Found {num_duplicates} duplicates")


def _time_str(time_in_millis: int, version: tuple | None) -> str:
    try:
        timezone = TIMEZONE_UTC
        if version and version <= (5, 3, 9):
            timezone = TIMEZONE_OSLO
        return datetime.fromtimestamp(time_in_millis / 1000, tz=timezone).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    except Exception:
        return "????-??-??T??:??:??.???"

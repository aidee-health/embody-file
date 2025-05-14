"""Parser module for embodyfile package."""

import logging
from datetime import datetime
from functools import reduce
from io import BufferedReader

import statistics
from collections import defaultdict
from embodycodec import file_codec

from .models import Data
from .models import DeviceInfo
from .models import ProtocolMessageDict
from .parser_utils import time_str, serial_no_to_hex

# Constants
MIN_TIMESTAMP = datetime(1999, 10, 1, 0, 0).timestamp() * 1000
MAX_TIMESTAMP = datetime(2036, 10, 1, 0, 0).timestamp() * 1000
DEFAULT_ECG_PPG_SAMPLERATE = 1000.0  # Default sample rate for ECG and PPG data

# Constants for LSB timestamp reconstruction
LSB_TIMESTAMP_WRAP_UPPER_THRESHOLD = 65000
LSB_TIMESTAMP_WRAP_LOWER_THRESHOLD = 100
LSB_TIMESTAMP_WRAP_ADJUSTMENT = 0x10000  # 65536, for 16-bit wrap

TIMESTAMP_JUMP_THRESHOLD_MS = 1000

# Constants for sample rate estimation and snapping
KNOWN_STANDARD_SAMPLE_RATES_HZ = [100.0, 125.0, 250.0, 500.0, 1000.0, 2000.0]
# Derived constant, ensure it's defined after KNOWN_STANDARD_SAMPLE_RATES_HZ
KNOWN_STANDARD_SAMPLE_INTERVALS_MS = sorted([1000.0 / r for r in KNOWN_STANDARD_SAMPLE_RATES_HZ])
SAMPLE_INTERVAL_SNAP_TOLERANCE_PERCENTAGE = 0.05  # 5% tolerance for snapping


def read_data(f: BufferedReader, fail_on_errors=False, sample_rate: float | None = None) -> Data:
    """Parse data from file into memory. Throws LookupError if no Header is found."""
    collections = _read_data_in_memory(f, fail_on_errors)
    samplerate = sample_rate
    if file_codec.PulseBlockEcg in collections or file_codec.PulseBlockPpg in collections:
        if samplerate is None:
            samplerate = _estimate_samplerate(collections)
        __convert_block_messages_to_pulse_list(collections, samplerate)
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

    serial = serial_no_to_hex(header.serial)
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
        samplerate,
    )


def _read_data_in_memory(f: BufferedReader, fail_on_errors=False) -> ProtocolMessageDict:
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
                serial = serial_no_to_hex(header.serial)
                if MAX_TIMESTAMP < header.current_time:
                    err_msg = (
                        f"{start_pos_of_current_msg}: Received full timestamp "
                        f"({header.current_time}/{time_str(header.current_time, version)}) is"
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
                    f"{header.current_time}/{time_str(header.current_time, version)}"
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
                        f"({current_time}/{time_str(current_time, version)}) is greater than "
                        f"max({MAX_TIMESTAMP}). Skipping"
                    )
                    if fail_on_errors:
                        raise LookupError(err_msg)
                    if logging.getLogger().isEnabledFor(logging.WARNING):
                        logging.warning(err_msg)
                elif current_time < last_full_timestamp:
                    err_msg = (
                        f"{start_pos_of_current_msg}: Received full timestamp "
                        f"({current_time}/{time_str(current_time, version)}) is less "
                        f"than last_full_timestamp ({last_full_timestamp}/{time_str(last_full_timestamp, version)})"
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
                _add_msg_to_collections(msg.time, msg, collections)
                continue

            if current_timestamp < MIN_TIMESTAMP:
                too_old_msgs += 1
                err_msg = (
                    f"{start_pos_of_current_msg}: Timestamp is too old "
                    f"({current_timestamp}/{time_str(current_timestamp, version)}). Still adding message"
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
            if (
                original_two_lsbs > LSB_TIMESTAMP_WRAP_UPPER_THRESHOLD
                and two_lsb_of_timestamp < LSB_TIMESTAMP_WRAP_LOWER_THRESHOLD
            ):
                current_timestamp += (
                    LSB_TIMESTAMP_WRAP_ADJUSTMENT  # wrapped counter, incr byte 3 (first after two least sign. bytes)
                )
                lsb_wrap_counter += 1
            elif (
                two_lsb_of_timestamp > LSB_TIMESTAMP_WRAP_UPPER_THRESHOLD
                and original_two_lsbs < LSB_TIMESTAMP_WRAP_LOWER_THRESHOLD
            ):
                # corner case - we've received an older, pre-wrapped message
                current_timestamp -= LSB_TIMESTAMP_WRAP_ADJUSTMENT
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
                        f"timestamp={time_str(current_timestamp, version)}"
                    )

            if prev_timestamp > 0 and current_timestamp > prev_timestamp + TIMESTAMP_JUMP_THRESHOLD_MS:
                jump = current_timestamp - prev_timestamp
                err_msg = (
                    f"Jump > 1 sec - Message #{total_messages + 1} "
                    f"timestamp={current_timestamp}/{time_str(current_timestamp, version)} "
                    f"Previous message timestamp={prev_timestamp}/{time_str(prev_timestamp, version)} "
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
        f"Parsed {total_messages} messages in time range {time_str(start_timestamp, version)} "
        f"to {time_str(current_timestamp, version)}, "
        f"with {unknown_msgs} unknown, {too_old_msgs} too old, {back_leap_msgs} backward leaps (>100 ms backwards), "
        f"{out_of_seq_msgs} out of sequence"
    )

    return collections


def _process_sensor_channel_data(
    sensor_messages: list[tuple[int, file_codec.PulseBlockEcg | file_codec.PulseBlockPpg]],
    locked_initial_timestamps: list[int],
    sample_counters: list[int],
    block_counters: list[int],
    early_counters: list[int],
    late_counters: list[int],
    dup_timestamps: list[int],
    merged_data: dict[int, file_codec.PulseRawList],
    sampleinterval_ms: float,
    stamp_tol: float,
    stamp_gap_limit: float,
    overall_max_ecg_channels: int,
    overall_max_ppg_channels: int,
    is_ecg: bool,
) -> None:
    """Helper function to process PulseBlockEcg or PulseBlockPpg messages for a single channel type."""
    sensor_name = "ECG" if is_ecg else "PPG"
    if not sensor_messages:
        return

    for _, block in sensor_messages:
        channel = block.channel
        block_time = block.time

        if locked_initial_timestamps[channel] == 0:
            locked_initial_timestamps[channel] = block_time
        else:
            # Check the accuracy/skew of the calculated timestamp vs the block timestamp
            first_samplestamp_expected = (
                locked_initial_timestamps[channel] + sample_counters[channel] * sampleinterval_ms
            )
            stamp_diff = first_samplestamp_expected - block_time  # Positive means block timestamps are too early

            if stamp_diff > stamp_tol:
                early_counters[channel] += 1
            elif stamp_diff < -stamp_tol:
                late_counters[channel] += 1
                if stamp_diff < -stamp_gap_limit:  # Treat gaps larger than stamp_gap_limit as skips
                    locked_initial_timestamps[channel] = block_time  # Take new locked time
                    sample_counters[channel] = 0  # Reset counter
                    if logging.getLogger().isEnabledFor(logging.INFO):
                        logging.info(
                            f"{sensor_name}{channel} block {block_counters[channel]} has late timestamp "
                            f"of {block_time} but was expecting {first_samplestamp_expected}"
                        )

        for sample_value in block.samples:
            samplestamp = int(locked_initial_timestamps[channel] + sample_counters[channel] * sampleinterval_ms)

            if samplestamp not in merged_data:
                merged_data[samplestamp] = file_codec.PulseRawList(
                    format=0,
                    no_of_ecgs=overall_max_ecg_channels,
                    no_of_ppgs=overall_max_ppg_channels,
                    ecgs=[0] * overall_max_ecg_channels,  # Initialize with 0 as per original logic
                    ppgs=[0] * overall_max_ppg_channels,
                )

            target_list = merged_data[samplestamp].ecgs if is_ecg else merged_data[samplestamp].ppgs

            # Ensure channel index is within bounds (should be, due to max_channels calculation)
            if channel < len(target_list):
                if (
                    target_list[channel] != 0 and target_list[channel] is not None
                ):  # Check if data already entered (original was [0], so check against 0)
                    dup_timestamps[channel] += 1
                    if logging.getLogger().isEnabledFor(logging.DEBUG):
                        logging.debug(
                            f"{sensor_name}{channel} sample {sample_counters[channel]} from block "
                            f"{block_counters[channel]} has duplicate timestamp {samplestamp}. "
                            f"Value {target_list[channel]} overwritten by {int(sample_value)}."
                        )

                value_to_store = int(sample_value)
                if not is_ecg:  # PPG values are inverted
                    value_to_store = -value_to_store
                target_list[channel] = value_to_store
            elif logging.getLogger().isEnabledFor(logging.WARNING):
                logging.warning(
                    f"Channel index {channel} out of bounds for {sensor_name} list (len {len(target_list)}) at timestamp {samplestamp}."
                )

            sample_counters[channel] += 1
        block_counters[channel] += 1


def __convert_block_messages_to_pulse_list(
    collections: ProtocolMessageDict,
    samplerate: float = DEFAULT_ECG_PPG_SAMPLERATE,
    stamp_tol: float = 0.95,
    stamp_gap_limit: float = 5.0,
) -> None:
    """Converts ecg and ppg block messages to pulse list messages."""
    ecg_messages: list[tuple[int, file_codec.PulseBlockPpg | file_codec.PulseBlockEcg]] | None = collections.get(
        file_codec.PulseBlockEcg
    )
    ppg_messages: list[tuple[int, file_codec.PulseBlockPpg | file_codec.PulseBlockEcg]] | None = collections.get(
        file_codec.PulseBlockPpg
    )

    # Ensure messages exist, otherwise, nothing to do.
    if not ecg_messages and not ppg_messages:
        logging.info("No PulseBlockEcg or PulseBlockPpg messages to convert.")
        return

    sampleinterval_ms = 1000 / samplerate
    merged_data: dict[int, file_codec.PulseRawList] = {}

    # Determine max channels from the data itself
    # These represent the count of channels (e.g., if max index is 0, count is 1)
    current_max_ecg_channels = 0
    if ecg_messages:
        for _, ecg_block in ecg_messages:
            current_max_ecg_channels = max(ecg_block.channel + 1, current_max_ecg_channels)

    current_max_ppg_channels = 0
    if ppg_messages:
        for _, ppg_block in ppg_messages:
            current_max_ppg_channels = max(ppg_block.channel + 1, current_max_ppg_channels)

    # Initialize tracking lists for ECG
    locked_initial_ecg_timestamp = [0] * current_max_ecg_channels
    ecg_sample_counters = [0] * current_max_ecg_channels
    ecg_block_counters = [0] * current_max_ecg_channels
    ecg_early_counters = [0] * current_max_ecg_channels
    ecg_late_counters = [0] * current_max_ecg_channels
    dup_ecg_timestamps = [0] * current_max_ecg_channels

    # Initialize tracking lists for PPG
    locked_initial_ppg_timestamp = [0] * current_max_ppg_channels
    ppg_sample_counters = [0] * current_max_ppg_channels
    ppg_block_counters = [0] * current_max_ppg_channels
    ppg_early_counters = [0] * current_max_ppg_channels
    ppg_late_counters = [0] * current_max_ppg_channels
    dup_ppg_timestamps = [0] * current_max_ppg_channels

    # Process ECG messages
    if ecg_messages:
        _process_sensor_channel_data(
            sensor_messages=ecg_messages,
            locked_initial_timestamps=locked_initial_ecg_timestamp,
            sample_counters=ecg_sample_counters,
            block_counters=ecg_block_counters,
            early_counters=ecg_early_counters,
            late_counters=ecg_late_counters,
            dup_timestamps=dup_ecg_timestamps,
            merged_data=merged_data,
            sampleinterval_ms=sampleinterval_ms,
            stamp_tol=stamp_tol,
            stamp_gap_limit=stamp_gap_limit,
            overall_max_ecg_channels=current_max_ecg_channels,
            overall_max_ppg_channels=current_max_ppg_channels,
            is_ecg=True,
        )

    # Process PPG messages
    if ppg_messages:
        _process_sensor_channel_data(
            sensor_messages=ppg_messages,
            locked_initial_timestamps=locked_initial_ppg_timestamp,
            sample_counters=ppg_sample_counters,
            block_counters=ppg_block_counters,
            early_counters=ppg_early_counters,
            late_counters=ppg_late_counters,
            dup_timestamps=dup_ppg_timestamps,
            merged_data=merged_data,
            sampleinterval_ms=sampleinterval_ms,
            stamp_tol=stamp_tol,
            stamp_gap_limit=stamp_gap_limit,
            overall_max_ecg_channels=current_max_ecg_channels,
            overall_max_ppg_channels=current_max_ppg_channels,
            is_ecg=False,
        )

    # Logging and finalization
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        num_ecg_samples = sum(len(block.samples) for _, block in ecg_messages) if ecg_messages else 0
        num_ppg_samples = sum(len(block.samples) for _, block in ppg_messages) if ppg_messages else 0
        logging.debug(
            f"Converted {num_ecg_samples} ECG samples and {num_ppg_samples} PPG samples "
            f"from block messages to {len(merged_data)} PulseRawList messages."
        )

    if logging.getLogger().isEnabledFor(logging.INFO):
        for chan in range(current_max_ecg_channels):
            if dup_ecg_timestamps[chan] > 0:
                logging.info(f"Duplicate timestamp count for ECG{chan}: {dup_ecg_timestamps[chan]}")
            if ecg_late_counters[chan] > 0:
                logging.info(f"ECG{chan} has {ecg_late_counters[chan]} blocks with late timestamps.")
            if ecg_early_counters[chan] > 0:
                logging.info(f"ECG{chan} has {ecg_early_counters[chan]} blocks with early timestamps.")

        for chan in range(current_max_ppg_channels):
            if dup_ppg_timestamps[chan] > 0:
                logging.info(f"Duplicate timestamp count for PPG{chan}: {dup_ppg_timestamps[chan]}")
            if ppg_late_counters[chan] > 0:
                logging.info(f"PPG{chan} has {ppg_late_counters[chan]} blocks with late timestamps.")
            if ppg_early_counters[chan] > 0:
                logging.info(f"PPG{chan} has {ppg_early_counters[chan]} blocks with early timestamps.")

    collections[file_codec.PulseRawList] = list(merged_data.items())
    # Sort by timestamp for ordered output, though dict iteration order is generally insertion order in modern Python
    collections[file_codec.PulseRawList].sort(key=lambda item: item[0])

    if logging.getLogger().isEnabledFor(logging.DEBUG):
        for timestamp, prl in collections[file_codec.PulseRawList]:
            # Check if all expected channels have data, assuming 0 means no data
            actual_ppg_channels_with_data = sum(1 for x in prl.ppgs[:current_max_ppg_channels] if x != 0)
            actual_ecg_channels_with_data = sum(1 for x in prl.ecgs[:current_max_ecg_channels] if x != 0)

            if prl.no_of_ppgs > 0 and actual_ppg_channels_with_data == 0:
                logging.debug(f"{timestamp} - Potentially missing all PPG data for entry {prl}")
            if prl.no_of_ecgs > 0 and actual_ecg_channels_with_data == 0:
                logging.debug(f"{timestamp} - Potentially missing all ECG data for entry {prl}")

    # Clear the original block messages as they've been converted
    if file_codec.PulseBlockPpg in collections:
        collections[file_codec.PulseBlockPpg] = []
    if file_codec.PulseBlockEcg in collections:
        collections[file_codec.PulseBlockEcg] = []


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


def _estimate_samplerate(collections: ProtocolMessageDict) -> float:
    """Estimates the sample rate from PulseBlockEcg and PulseBlockPpg messages.

    Args:
        collections: The dictionary of parsed protocol messages.
        default_samplerate: The samplerate to return if estimation is not possible.

    Returns:
        The estimated sample rate in Hz, or the default_samplerate if estimation fails.
    """
    all_estimated_intervals_ms: list[float] = []

    def process_blocks_for_sr(
        block_messages: list[tuple[int, file_codec.PulseBlockEcg | file_codec.PulseBlockPpg]] | None,
        sensor_type: str,
    ) -> None:
        if not block_messages:
            return

        blocks_by_channel: defaultdict[int, list[file_codec.PulseBlockEcg | file_codec.PulseBlockPpg]] = defaultdict(
            list
        )
        for _, block in block_messages:
            blocks_by_channel[block.channel].append(block)

        for channel_id, channel_blocks in blocks_by_channel.items():
            if len(channel_blocks) < 2 and logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(
                    f"Not enough blocks for {sensor_type} channel {channel_id} to estimate interval (found {len(channel_blocks)})."
                )
                continue

            # Sort blocks by their start time to ensure correct sequential processing
            channel_blocks.sort(key=lambda b: b.time)

            for i in range(len(channel_blocks) - 1):
                block1 = channel_blocks[i]
                block2 = channel_blocks[i + 1]

                num_samples_b1 = len(block1.samples)
                if num_samples_b1 == 0 and logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.debug(
                        f"{sensor_type} channel {channel_id}, block at time {block1.time} has no samples, skipping for SR estimation."
                    )
                    continue

                time_delta_ms = float(block2.time - block1.time)

                if time_delta_ms <= 0 and logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.debug(
                        f"Non-positive time delta ({time_delta_ms}ms) between consecutive blocks for {sensor_type} "
                        f"channel {channel_id} (block1 time: {block1.time}, block2 time: {block2.time}), skipping pair."
                    )
                    continue

                interval = time_delta_ms / num_samples_b1
                all_estimated_intervals_ms.append(interval)

    ecg_block_msgs = collections.get(file_codec.PulseBlockEcg)
    ppg_block_msgs = collections.get(file_codec.PulseBlockPpg)

    process_blocks_for_sr(ecg_block_msgs, "ECG")
    process_blocks_for_sr(ppg_block_msgs, "PPG")

    if not all_estimated_intervals_ms:
        logging.warning(
            f"Could not estimate sample rate from block messages. No valid block pairs found. Falling back to default: {DEFAULT_ECG_PPG_SAMPLERATE} Hz."
        )
        return DEFAULT_ECG_PPG_SAMPLERATE

    try:
        # Using median for robustness against outliers
        median_interval_ms = statistics.median(all_estimated_intervals_ms)
    except statistics.StatisticsError:
        logging.warning(
            f"Statistics error while calculating median interval (list was likely empty despite checks). Falling back to default: {DEFAULT_ECG_PPG_SAMPLERATE} Hz."
        )
        return DEFAULT_ECG_PPG_SAMPLERATE

    if median_interval_ms <= 0:
        logging.warning(
            f"Estimated median sample interval is non-positive ({median_interval_ms:.3f}ms). "
            f"Falling back to default samplerate: {DEFAULT_ECG_PPG_SAMPLERATE} Hz."
        )
        return DEFAULT_ECG_PPG_SAMPLERATE

    final_interval_ms = median_interval_ms
    snapped = False

    closest_known_interval = min(KNOWN_STANDARD_SAMPLE_INTERVALS_MS, key=lambda x: abs(x - median_interval_ms))

    # Check if the median_interval_ms is within tolerance of the closest_known_interval
    if (
        abs(median_interval_ms - closest_known_interval) / closest_known_interval
        <= SAMPLE_INTERVAL_SNAP_TOLERANCE_PERCENTAGE
    ):
        final_interval_ms = closest_known_interval
        snapped = True
        logging.info(
            f"Snapped calculated median interval {median_interval_ms:.3f}ms to known interval {final_interval_ms:.3f}ms."
        )
    else:
        logging.info(
            f"Calculated median interval {median_interval_ms:.3f}ms is outside {SAMPLE_INTERVAL_SNAP_TOLERANCE_PERCENTAGE * 100:.0f}% tolerance "
            f"of closest known interval {closest_known_interval:.3f}ms. Using calculated median."
        )

    estimated_sr = 1000.0 / final_interval_ms

    log_message = (
        f"Estimated sample rate: {estimated_sr:.2f} Hz from {len(all_estimated_intervals_ms)} observed block intervals "
        f"(final interval: {final_interval_ms:.3f}ms"
    )
    if snapped:
        log_message += f", snapped from median {median_interval_ms:.3f}ms)."
    else:
        log_message += ", used calculated median directly)."

    logging.info(log_message)

    return estimated_sr


def _analyze_timestamps(data: list[tuple[int, file_codec.ProtocolMessage]]) -> None:
    """Analyze timestamp patterns in the data.

    This function efficiently analyzes timestamp sequences to detect:
    - Duplicates: Multiple messages with identical timestamps
    - Big time leaps: Jumps of more than 20ms between consecutive messages
    - Small time leaps: Jumps between 5-20ms between consecutive messages

    Args:
        data: List of timestamp and message tuples
    """
    if not logging.getLogger().isEnabledFor(logging.DEBUG):
        return

    # Extract timestamps once and store in a tuple for better performance
    ts = tuple(x[0] for x in data)

    if not ts:
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

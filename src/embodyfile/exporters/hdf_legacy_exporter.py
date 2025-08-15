"""HDF exporter implementation."""

import logging
import sys
from dataclasses import astuple
from dataclasses import fields
from pathlib import Path

import pandas as pd
import pytz
from embodycodec import file_codec

from ..models import Data
from ..models import ProtocolMessageOrChildren
from . import BaseExporter
from .common import ensure_directory, export_device_info_to_dataframe, log_export_start


class HDFLegacyExporter(BaseExporter):
    """Legacy HDF exporter for AideeLab compatibility."""

    # Define file extension for HDF files
    FILE_EXTENSION = "hdf"

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to legacy HDF format."""
        log_export_start("Legacy HDF", output_path)

        # Add extension if not present
        if output_path.suffix.lower() != f".{self.FILE_EXTENSION}":
            output_path = output_path.with_suffix(f".{self.FILE_EXTENSION}")

        # Create parent directory if it doesn't exist
        ensure_directory(output_path)

        logging.info(f"Converting data to HDF: {output_path}")

        df_multidata = _multi_data2pandas(data.multi_ecg_ppg_data).astype("int32")
        df_data = _to_pandas(data.sensor).astype("int32")
        df_afe = _to_pandas(data.afe)
        df_temp = _to_pandas(data.temp).astype("int16")
        df_hr = _to_pandas(data.hr).astype("int16")

        if not data.acc or not data.gyro:
            logging.warning(f"No IMU data: {output_path}")
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

        # Use multiple to_hdf calls for stability with legacy format
        # Note: While using a single HDFStore context is more efficient,
        # it can cause cleanup errors with some PyTables versions.
        # For backward compatibility, we use the original approach.
        df_data.to_hdf(output_path, key="data", mode="w", complevel=4)

        # Store multidata with frequency as metadata attribute
        with pd.HDFStore(output_path, mode="a") as store:
            store.put("multidata", df_multidata, format="table", complevel=4)
            if data.ecg_ppg_sample_frequency:
                # Store the sampling frequency as metadata
                store.get_storer("multidata").attrs.sample_frequency_hz = data.ecg_ppg_sample_frequency
                store.get_storer("multidata").attrs.sample_period_ms = 1000.0 / data.ecg_ppg_sample_frequency

        df_imu.to_hdf(output_path, key="imu", mode="a", complevel=4)
        df_afe.to_hdf(output_path, key="afe", mode="a", complevel=4)
        df_temp.to_hdf(output_path, key="temp", mode="a", complevel=4)
        df_hr.to_hdf(output_path, key="hr", mode="a", complevel=4)

        # Export device info
        device_info = export_device_info_to_dataframe(data)
        if device_info is not None:
            device_info.to_hdf(output_path, key="device_info", mode="a", complevel=4)

        logging.info(f"Exported all data to HDF file: {output_path}")

    def _export_dataframe(self, data: Data, df: pd.DataFrame, file_path: Path, schema_name: str) -> None:
        """Not implemented for legacy exporter."""
        pass


def _to_pandas(data: list[tuple[int, ProtocolMessageOrChildren]]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()

    columns = ["timestamp"] + [f.name for f in fields(data[0][1])]
    column_data = [(ts, *astuple(d)) for ts, d in data]

    df = pd.DataFrame(column_data, columns=columns)
    df = df.set_index("timestamp")
    df.index = pd.to_datetime(df.index, unit="ms").tz_localize(pytz.utc)
    df = df[~df.index.duplicated()]
    df = df.sort_index()
    df = df[df[df.columns] < sys.maxsize].dropna()  # remove badly converted values
    return df


def _multi_data2pandas(data: list[tuple[int, file_codec.PulseRawList]]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()

    num_ecg = data[0][1].no_of_ecgs
    num_ppg = data[0][1].no_of_ppgs

    columns = ["timestamp"] + [f"ecg_{i}" for i in range(num_ecg)] + [f"ppg_{i}" for i in range(num_ppg)]

    column_data = [
        (ts, *tuple(d.ecgs), *tuple(d.ppgs)) for ts, d in data if d.no_of_ecgs == num_ecg and d.no_of_ppgs == num_ppg
    ]

    df = pd.DataFrame(column_data, columns=columns)
    df = df.set_index("timestamp")
    df.index = pd.to_datetime(df.index, unit="ms").tz_localize(pytz.utc)
    df = df[~df.index.duplicated()]
    df = df.sort_index()

    return df

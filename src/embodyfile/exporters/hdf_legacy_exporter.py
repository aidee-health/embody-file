"""HDF exporter implementation."""

import logging
import sys
from dataclasses import asdict
from dataclasses import astuple
from dataclasses import fields
from pathlib import Path

import pandas as pd
import pytz
from embodycodec import file_codec

from ..models import Data
from ..models import ProtocolMessageOrChildren
from . import BaseExporter


class HDFLegacyExporter(BaseExporter):
    """Exporter for HDF format with all schemas in the same file."""

    # Define file extension for HDF files
    FILE_EXTENSION = "hdf"

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to a single HDF file with multiple datasets."""
        logging.info(f"Exporting data to HDF: {output_path}")

        # Add extension if not present
        if output_path.suffix.lower() != f".{self.FILE_EXTENSION}":
            output_path = output_path.with_suffix(f".{self.FILE_EXTENSION}")

        # Create parent directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

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

        df_data.to_hdf(output_path, key="data", mode="w", complevel=4)
        df_multidata.to_hdf(output_path, key="multidata", mode="a", complevel=4)
        df_imu.to_hdf(output_path, key="imu", mode="a", complevel=4)
        df_afe.to_hdf(output_path, key="afe", mode="a", complevel=4)
        df_temp.to_hdf(output_path, key="temp", mode="a", complevel=4)
        df_hr.to_hdf(output_path, key="hr", mode="a", complevel=4)

        info = {k: [v] for k, v in asdict(data.device_info).items()}
        pd.DataFrame(info).to_hdf(output_path, key="device_info", mode="a", complevel=4)

        logging.info(f"Exported all data to HDF file: {output_path}")

    def _export_dataframe(self, df: pd.DataFrame, file_path: Path, schema_name: str) -> None:
        """Export a dataframe to CSV.Currently not in use, since we are using legacy handling for HDF for now."""
        pass


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

    columns = ["timestamp"] + [f"ecg_{i}" for i in range(num_ecg)] + [f"ppg_{i}" for i in range(num_ppg)]

    column_data = [
        (ts, *tuple(d.ecgs), *tuple(d.ppgs)) for ts, d in data if d.no_of_ecgs == num_ecg and d.no_of_ppgs == num_ppg
    ]

    df = pd.DataFrame(column_data, columns=columns)
    df.set_index("timestamp", inplace=True)
    df.index = pd.to_datetime(df.index, unit="ms").tz_localize(pytz.utc)
    df = df[~df.index.duplicated()]
    df.sort_index(inplace=True)

    return df

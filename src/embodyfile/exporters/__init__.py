"""Base class for exporters."""

from abc import ABC
from abc import abstractmethod
from dataclasses import astuple
from dataclasses import fields
from pathlib import Path
from typing import Any

import pandas as pd
import pytz

from ..models import Data


class BaseExporter(ABC):
    """Base class for data exporters."""

    @abstractmethod
    def export(self, data: Data, output_path: Path) -> None:
        """Export data to a specific format.

        Args:
            data: The data to export
            output_path: Path where the output should be saved
        """
        pass

    def _to_pandas(self, data: list[tuple[int, Any]]) -> pd.DataFrame:
        """Convert data to pandas DataFrame.

        Args:
            data: List of timestamp and data tuples

        Returns:
            DataFrame with the data
        """
        if not data:
            return pd.DataFrame()

        columns = ["timestamp"] + [f.name for f in fields(data[0][1])]
        column_data = [(ts, *astuple(d)) for ts, d in data]

        df = pd.DataFrame(column_data, columns=columns)
        df.set_index("timestamp", inplace=True)
        df.index = pd.to_datetime(df.index, unit="ms").tz_localize(pytz.utc)
        df = df[~df.index.duplicated()]
        df.sort_index(inplace=True)
        return df

    def _multi_data2pandas(self, data: list[tuple[int, Any]]) -> pd.DataFrame:
        """Convert multi-channel data to pandas DataFrame.

        Args:
            data: List of timestamp and multi-channel data tuples

        Returns:
            DataFrame with the multi-channel data
        """
        if not data:
            return pd.DataFrame()

        num_ecg = data[0][1].no_of_ecgs
        num_ppg = data[0][1].no_of_ppgs

        columns = (
            ["timestamp"]
            + [f"ecg_{i}" for i in range(num_ecg)]
            + [f"ppg_{i}" for i in range(num_ppg)]
        )

        column_data = [
            (ts,) + tuple(d.ecgs) + tuple(d.ppgs)
            for ts, d in data
            if d.no_of_ecgs == num_ecg and d.no_of_ppgs == num_ppg
        ]

        df = pd.DataFrame(column_data, columns=columns)
        df.set_index("timestamp", inplace=True)
        df.index = pd.to_datetime(df.index, unit="ms").tz_localize(pytz.utc)
        df = df[~df.index.duplicated()]
        df.sort_index(inplace=True)

        return df

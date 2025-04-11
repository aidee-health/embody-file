"""HDF exporter implementation."""

import logging
import sys
from dataclasses import asdict
from pathlib import Path

from ..models import Data
from . import BaseExporter


class HDFExporter(BaseExporter):
    """Exporter for HDF format."""

    def export(self, data: Data, output_path: Path) -> None:
        """Export data to HDF format.

        Args:
            data: The data to export
            output_path: Path where the HDF file should be saved
        """
        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Converting data to HDF: {output_path}")

        df_multidata = self._multi_data2pandas(data.multi_ecg_ppg_data).astype("int32")
        df_data = self._to_pandas(data.sensor).astype("int32")
        df_afe = self._to_pandas(data.afe)
        df_temp = self._to_pandas(data.temp).astype("int16")
        df_hr = self._to_pandas(data.hr).astype("int16")

        if not data.acc or not data.gyro:
            if logging.getLogger().isEnabledFor(logging.WARNING):
                logging.warning(f"No IMU data: {output_path}")
            df_imu = self._to_pandas([])
        else:
            import pandas as pd

            df_imu = pd.merge_asof(
                self._to_pandas(data.acc),
                self._to_pandas(data.gyro),
                left_index=True,
                right_index=True,
                tolerance=pd.Timedelta("2ms"),
                direction="nearest",
            )

        # Filter out values that are too large
        df_data = df_data[df_data[df_data.columns] < sys.maxsize].dropna()
        df_multidata = df_multidata[
            df_multidata[df_multidata.columns] < sys.maxsize
        ].dropna()

        df_data.to_hdf(output_path, key="data", mode="w")
        df_multidata.to_hdf(output_path, key="multidata", mode="a")
        df_imu.to_hdf(output_path, key="imu", mode="a")
        df_afe.to_hdf(output_path, key="afe", mode="a")
        df_temp.to_hdf(output_path, key="temp", mode="a")
        df_hr.to_hdf(output_path, key="hr", mode="a")

        info = {k: [v] for k, v in asdict(data.device_info).items()}
        import pandas as pd

        pd.DataFrame(info).to_hdf(output_path, key="device_info", mode="a")

        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info(f"Converted data to HDF: {output_path}")

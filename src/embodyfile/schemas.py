"""Schema definitions for sensor data exports."""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import ClassVar
from typing import Optional


class DataType(Enum):
    """Types of data that can be exported."""

    PHYSIO = "physio"  # Combined ECG/PPG data
    ACCELEROMETER = "acc"  # Accelerometer data
    GYROSCOPE = "gyro"  # Gyroscope data
    TEMPERATURE = "temp"  # Temperature data
    HEART_RATE = "hr"  # Heart rate data
    AFE = "afe"  # AFE settings
    BATTERY_DIAG = "battdiag"  # Battery diagnostic data


@dataclass
class ExportSchema:
    """Schema definition for data export."""

    name: str  # Schema name (used in filenames)
    data_type: DataType  # Type of data this schema represents
    columns: list[str]  # Column names in order
    dtypes: dict[str, str]  # Data types for columns
    description: str = ""  # Human-readable description
    source_attributes: list[str] = field(
        default_factory=list
    )  # Attributes in Data model
    column_mapping: dict[str, str] = field(
        default_factory=dict
    )  # Mapping from source to schema columns
    hdf_key: Optional[str] = None  # Key to use for HDF format (if different from name)

    # Legacy mapping for HDF compatibility
    HDF_KEY_MAPPING: ClassVar[dict[DataType, str]] = {
        DataType.PHYSIO: "multidata",
        DataType.ACCELEROMETER: "imu",  # Special handling needed
        DataType.GYROSCOPE: "imu",  # Special handling needed
        DataType.TEMPERATURE: "temp",
        DataType.HEART_RATE: "hr",
        DataType.AFE: "afe",
        DataType.BATTERY_DIAG: "battdiag",
    }

    def __post_init__(self):
        """Validate schema after initialization."""
        # Ensure timestamp is the first column
        if "timestamp" not in self.columns:
            self.columns.insert(0, "timestamp")

        # Add timestamp dtype if not present
        if "timestamp" not in self.dtypes:
            self.dtypes["timestamp"] = "int64"

        # Set default HDF key if not provided
        if self.hdf_key is None and self.data_type in self.HDF_KEY_MAPPING:
            self.hdf_key = self.HDF_KEY_MAPPING[self.data_type]

    def get_output_path(self, base_path, timestamp=None):
        """Get the output path for this schema."""
        stem = Path(base_path).stem
        parent = Path(base_path).parent
        suffix = Path(base_path).suffix

        if timestamp:
            if isinstance(timestamp, (int, float)):
                # Convert milliseconds to datetime
                dt = datetime.fromtimestamp(timestamp / 1000.0)
                timestamp_str = dt.strftime("%Y%m%d_%H%M%S")
            elif isinstance(timestamp, datetime):
                timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
            else:
                timestamp_str = str(timestamp)

            return parent / f"{stem}_{self.name}_{timestamp_str}{suffix}"
        else:
            return parent / f"{stem}_{self.name}{suffix}"


class SchemaRegistry:
    """Registry of available export schemas."""

    # Standard schemas
    SCHEMAS = {
        # Combined ECG/PPG Schema
        DataType.PHYSIO: ExportSchema(
            name="physio",
            data_type=DataType.PHYSIO,
            columns=["timestamp", "ecg", "ppg", "ppg_red", "ppg_ir"],
            dtypes={
                "timestamp": "int64",
                "ecg": "int32",
                "ppg": "int32",
                "ppg_red": "int32",
                "ppg_ir": "int32",
            },
            description="Combined ECG and PPG physiological data",
            source_attributes=["multi_ecg_ppg_data", "sensor"],
            column_mapping={
                "ecg_0": "ecg",
                "ppg_0": "ppg",
                "ppg_1": "ppg_red",
                "ppg_2": "ppg_ir",
            },
            hdf_key="multidata",  # Legacy HDF key
        ),
        # Accelerometer Schema (separate from gyro due to different sampling rates)
        DataType.ACCELEROMETER: ExportSchema(
            name="accelerometer",
            data_type=DataType.ACCELEROMETER,
            columns=["timestamp", "acc_x", "acc_y", "acc_z"],
            dtypes={
                "timestamp": "int64",
                "acc_x": "int32",
                "acc_y": "int32",
                "acc_z": "int32",
            },
            description="Accelerometer data (208 Hz)",
            source_attributes=["acc"],
            column_mapping={"x": "acc_x", "y": "acc_y", "z": "acc_z"},
            hdf_key="imu",  # Special handling in HDF exporter
        ),
        # Gyroscope Schema (separate from accelerometer due to different sampling rates)
        DataType.GYROSCOPE: ExportSchema(
            name="gyroscope",
            data_type=DataType.GYROSCOPE,
            columns=["timestamp", "gyro_x", "gyro_y", "gyro_z"],
            dtypes={
                "timestamp": "int64",
                "gyro_x": "int32",
                "gyro_y": "int32",
                "gyro_z": "int32",
            },
            description="Gyroscope data (28 Hz)",
            source_attributes=["gyro"],
            column_mapping={"x": "gyro_x", "y": "gyro_y", "z": "gyro_z"},
            hdf_key="imu",  # Special handling in HDF exporter
        ),
        # Temperature Schema
        DataType.TEMPERATURE: ExportSchema(
            name="temp",
            data_type=DataType.TEMPERATURE,
            columns=["timestamp", "temp"],
            dtypes={"timestamp": "int64", "temp": "int16"},
            description="Temperature measurements",
            source_attributes=["temp"],
            column_mapping={
                "temperature": "temp"  # Handle potential column name difference
            },
            hdf_key="temp",
        ),
        # Heart Rate Schema
        DataType.HEART_RATE: ExportSchema(
            name="hr",
            data_type=DataType.HEART_RATE,
            columns=["timestamp", "hr"],
            dtypes={"timestamp": "int64", "hr": "int16"},
            description="Heart rate measurements",
            source_attributes=["hr"],
            column_mapping={
                "heart_rate": "hr"  # Handle potential column name difference
            },
            hdf_key="hr",
        ),
        # AFE Settings Schema
        DataType.AFE: ExportSchema(
            name="afe",
            data_type=DataType.AFE,
            columns=[
                "timestamp",
                "led1",
                "led2",
                "led3",
                "led4",
                "off_dac",
                "relative_gain",
            ],
            dtypes={
                "timestamp": "int64",
                "led1": "int32",
                "led2": "int32",
                "led3": "int32",
                "led4": "int32",
                "off_dac": "int32",
                "relative_gain": "float32",
            },
            description="Analog front-end configuration settings",
            source_attributes=["afe"],
            hdf_key="afe",
        ),
        # Battery Diagnostic Schema
        DataType.BATTERY_DIAG: ExportSchema(
            name="battdiag",
            data_type=DataType.BATTERY_DIAG,
            columns=[
                "timestamp",
                "voltage",
                "current",
                "temperature",
                "remaining_capacity",
                "full_capacity",
                "remaining_energy",
                "full_energy",
            ],
            dtypes={
                "timestamp": "int64",
                "voltage": "float32",
                "current": "float32",
                "temperature": "float32",
                "remaining_capacity": "int32",
                "full_capacity": "int32",
                "remaining_energy": "int32",
                "full_energy": "int32",
            },
            description="Battery diagnostic data",
            source_attributes=["batt_diag"],
            hdf_key="battdiag",
        ),
    }

    # Extra schema for legacy "data" format in HDF
    SENSOR_DATA = ExportSchema(
        name="sensor_data",
        data_type=DataType.PHYSIO,
        columns=["timestamp", "ecg", "ppg"],
        dtypes={"timestamp": "int64", "ecg": "int32", "ppg": "int32"},
        description="Legacy sensor data format",
        source_attributes=["sensor"],
        hdf_key="data",
    )

    # Dictionary for custom schemas
    _custom_schemas: dict[str, ExportSchema] = {}

    @classmethod
    def get_schema(cls, data_type: DataType) -> ExportSchema:
        """Get schema by data type."""
        return cls.SCHEMAS[data_type]

    @classmethod
    def get_all_schemas(cls) -> list[ExportSchema]:
        """Get all registered schemas."""
        return list(cls.SCHEMAS.values()) + list(cls._custom_schemas.values())

    @classmethod
    def get_schemas_for_export(cls, include_legacy: bool = False) -> list[ExportSchema]:
        """Get schemas for export.

        Args:
            include_legacy: Whether to include legacy schemas

        Returns:
            List of schemas for export
        """
        schemas = cls.get_all_schemas()
        if include_legacy:
            schemas.append(cls.SENSOR_DATA)
        return schemas

    @classmethod
    def register_schema(cls, schema: ExportSchema) -> None:
        """Register a custom schema."""
        cls._custom_schemas[schema.name] = schema

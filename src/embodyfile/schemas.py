"""Schema definitions for sensor data exports."""

from dataclasses import dataclass
from dataclasses import field
from enum import Enum


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
    file_extension: str = ""  # File extension for this schema (empty for default)

    def __post_init__(self):
        """Validate schema after initialization."""
        # Ensure timestamp is the first column
        if "timestamp" not in self.columns:
            self.columns.insert(0, "timestamp")

        # Add timestamp dtype if not present
        if "timestamp" not in self.dtypes:
            self.dtypes["timestamp"] = "int64"

    def get_output_path(self, base_path, timestamp=None, extension=None):
        """Get the output path for this schema with the proper extension.

        Args:
            base_path: Base path for the output file
            timestamp: Optional timestamp to include in the filename
            extension: File extension to use (overrides schema's file_extension)

        Returns:
            Path with proper schema name and extension
        """
        from pathlib import Path

        base_path = Path(base_path)
        stem = base_path.stem
        parent = base_path.parent

        # Build the base filename without extension
        if timestamp:
            from datetime import datetime

            if isinstance(timestamp, (int, float)):
                # Convert milliseconds to datetime
                dt = datetime.fromtimestamp(timestamp / 1000.0)
                timestamp_str = dt.strftime("%Y%m%d_%H%M%S")
            elif isinstance(timestamp, datetime):
                timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
            else:
                timestamp_str = str(timestamp)

            filename = f"{stem}_{self.name}_{timestamp_str}"
        else:
            filename = f"{stem}_{self.name}"

        # Apply the extension (prioritize parameter over schema property)
        ext = extension or self.file_extension or base_path.suffix
        if ext and not ext.startswith("."):
            ext = f".{ext}"

        return parent / f"{filename}{ext}"


class SchemaRegistry:
    """Registry of available export schemas."""

    # Standard schemas
    SCHEMAS = {
        # Combined ECG/PPG Schema
        DataType.PHYSIO: ExportSchema(
            name="ecgppg",
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
        ),
        # Accelerometer Schema (separate from gyro due to different sampling rates)
        DataType.ACCELEROMETER: ExportSchema(
            name="acc",
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
        ),
        # Gyroscope Schema (separate from accelerometer due to different sampling rates)
        DataType.GYROSCOPE: ExportSchema(
            name="gyro",
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
    def get_schemas_for_export(cls) -> list[ExportSchema]:
        """Get schemas for export.

        Returns:
            List of schemas for export
        """
        return cls.get_all_schemas()

    @classmethod
    def register_schema(cls, schema: ExportSchema) -> None:
        """Register a custom schema."""
        cls._custom_schemas[schema.name] = schema

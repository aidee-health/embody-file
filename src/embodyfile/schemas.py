"""Schema definitions for sensor data exports."""

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from pathlib import Path

from .export_utils import get_output_path


class DataType(Enum):
    """Types of data that can be exported."""

    ECG_PPG = "ecg_ppg"  # Combined ECG/PPG data
    ACCELEROMETER = "acc"  # Accelerometer data
    GYROSCOPE = "gyro"  # Gyroscope data
    TEMPERATURE = "temp"  # Temperature data
    HEART_RATE = "hr"  # Heart rate data
    AFE = "afe"  # AFE settings
    BATTERY_DIAG = "battdiag"  # Battery diagnostic data
    DEVICE_INFO = "device_info"  # Device information


@dataclass
class ExportSchema:
    """Schema definition for data export."""

    name: str  # Schema name (used in filenames)
    data_type: DataType  # Type of data this schema represents
    columns: list[str]  # Column names in order
    description: str = ""  # Human-readable description
    source_attributes: list[str] = field(default_factory=list)  # Attributes in Data model
    column_mapping: dict[str, str] = field(default_factory=dict)  # Mapping from source to schema columns
    file_extension: str = ""  # File extension for this schema (empty for default)

    def __post_init__(self):
        """Validate schema after initialization."""
        # Ensure timestamp is the first column
        if "timestamp" not in self.columns:
            self.columns.insert(0, "timestamp")

    def get_output_path(self, base_path: Path, extension: str | None = None) -> Path:
        """Get the output path for this schema with the proper extension."""
        return get_output_path(base_path, self.name, extension if extension else self.file_extension)


class SchemaRegistry:
    """Registry of available export schemas."""

    # Standard schemas
    SCHEMAS = {
        DataType.ECG_PPG: ExportSchema(
            name="ecgppg",
            data_type=DataType.ECG_PPG,
            columns=["timestamp", "ecg", "ppg", "ppg_red", "ppg_ir"],
            description="Combined ECG and PPG physiological data",
            source_attributes=["multi_ecg_ppg_data", "sensor"],
            column_mapping={
                "ecg_0": "ecg",
                "ppg_0": "ppg",
                "ppg_1": "ppg_red",
                "ppg_2": "ppg_ir",
            },
        ),
        DataType.ACCELEROMETER: ExportSchema(
            name="acc",
            data_type=DataType.ACCELEROMETER,
            columns=["timestamp", "acc_x", "acc_y", "acc_z"],
            description="Accelerometer data (208 Hz)",
            source_attributes=["acc"],
            column_mapping={"x": "acc_x", "y": "acc_y", "z": "acc_z"},
        ),
        DataType.GYROSCOPE: ExportSchema(
            name="gyro",
            data_type=DataType.GYROSCOPE,
            columns=["timestamp", "gyro_x", "gyro_y", "gyro_z"],
            description="Gyroscope data (28 Hz)",
            source_attributes=["gyro"],
            column_mapping={"x": "gyro_x", "y": "gyro_y", "z": "gyro_z"},
        ),
        DataType.TEMPERATURE: ExportSchema(
            name="temp",
            data_type=DataType.TEMPERATURE,
            columns=["timestamp", "temp"],
            description="Temperature measurements",
            source_attributes=["temp"],
            column_mapping={"temperature": "temp"},
        ),
        DataType.HEART_RATE: ExportSchema(
            name="hr",
            data_type=DataType.HEART_RATE,
            columns=["timestamp", "hr"],
            description="Heart rate measurements",
            source_attributes=["hr"],
            column_mapping={"heart_rate": "hr"},
        ),
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
            description="Analog front-end configuration settings",
            source_attributes=["afe"],
        ),
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
            description="Battery diagnostic data",
            source_attributes=["batt_diag"],
        ),
    }

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

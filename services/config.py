"""Configuration management for the Payslip Intelligence Suite."""

import toml
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class AIConfig:
    provider: str
    model: str
    api_key_file: str


@dataclass
class ProcessingConfig:
    docs_folder: str
    archive_folder: str
    max_file_size_mb: int
    supported_formats: List[str]


@dataclass
class VerificationConfig:
    max_age_months: int
    min_consecutive_periods: int
    require_qualified_accountant_signature: bool


@dataclass
class FraudDetectionConfig:
    confidence_threshold: float
    font_consistency_check: bool
    total_validation: bool
    ocr_quality_threshold: float


@dataclass
class OutputConfig:
    log_level: str
    json_indent: int
    console_summary: bool


@dataclass
class Config:
    ai: AIConfig
    processing: ProcessingConfig
    verification: VerificationConfig
    fraud_detection: FraudDetectionConfig
    output: OutputConfig

    @classmethod
    def load(cls, config_path: str = "config.toml") -> "Config":
        """Load configuration from TOML file."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        data = toml.load(config_file)
        
        return cls(
            ai=AIConfig(**data["ai"]),
            processing=ProcessingConfig(**data["processing"]),
            verification=VerificationConfig(**data["verification"]),
            fraud_detection=FraudDetectionConfig(**data["fraud_detection"]),
            output=OutputConfig(**data["output"])
        )

    def get_api_key(self) -> str:
        """Load API key from the specified file."""
        key_path = Path(self.ai.api_key_file)
        if not key_path.exists():
            raise FileNotFoundError(f"API key file not found: {self.ai.api_key_file}")
        
        return key_path.read_text().strip()
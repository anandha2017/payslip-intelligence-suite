"""Tests for configuration management."""

import pytest
import tempfile
import toml
from pathlib import Path

from services.config import Config


def test_load_config(temp_dir):
    """Test loading configuration from TOML file."""
    config_data = {
        "ai": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key_file": ".secrets/test_key"
        },
        "processing": {
            "docs_folder": "test_docs",
            "archive_folder": "test_archive",
            "max_file_size_mb": 10,
            "supported_formats": ["pdf", "png"]
        },
        "verification": {
            "max_age_months": 6,
            "min_consecutive_periods": 3,
            "require_qualified_accountant_signature": False
        },
        "fraud_detection": {
            "confidence_threshold": 0.7,
            "font_consistency_check": True,
            "total_validation": True,
            "ocr_quality_threshold": 0.8
        },
        "output": {
            "log_level": "INFO",
            "json_indent": 2,
            "console_summary": True
        }
    }
    
    config_path = temp_dir / "test_config.toml"
    with open(config_path, 'w') as f:
        toml.dump(config_data, f)
    
    config = Config.load(str(config_path))
    
    assert config.ai.provider == "openai"
    assert config.ai.model == "gpt-4o-mini"
    assert config.processing.max_file_size_mb == 10
    assert config.verification.max_age_months == 6
    assert config.fraud_detection.confidence_threshold == 0.7
    assert config.output.log_level == "INFO"


def test_load_nonexistent_config():
    """Test loading non-existent configuration file."""
    with pytest.raises(FileNotFoundError):
        Config.load("nonexistent.toml")


def test_get_api_key(temp_dir):
    """Test API key loading."""
    api_key = "test-api-key-12345"
    key_file = temp_dir / "api_key"
    key_file.write_text(api_key)
    
    config_data = {
        "ai": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key_file": str(key_file)
        },
        "processing": {
            "docs_folder": "test_docs",
            "archive_folder": "test_archive",
            "max_file_size_mb": 10,
            "supported_formats": ["pdf"]
        },
        "verification": {
            "max_age_months": 6,
            "min_consecutive_periods": 3,
            "require_qualified_accountant_signature": False
        },
        "fraud_detection": {
            "confidence_threshold": 0.7,
            "font_consistency_check": True,
            "total_validation": True,
            "ocr_quality_threshold": 0.8
        },
        "output": {
            "log_level": "INFO",
            "json_indent": 2,
            "console_summary": True
        }
    }
    
    config_path = temp_dir / "test_config.toml"
    with open(config_path, 'w') as f:
        toml.dump(config_data, f)
    
    config = Config.load(str(config_path))
    assert config.get_api_key() == api_key


def test_get_nonexistent_api_key(sample_config):
    """Test loading non-existent API key file."""
    with pytest.raises(FileNotFoundError):
        sample_config.get_api_key()
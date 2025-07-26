"""Test configuration and shared fixtures."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, date
from unittest.mock import Mock

from services.config import Config, AIConfig, ProcessingConfig, VerificationConfig, FraudDetectionConfig, OutputConfig
from services.models import (
    DocumentAnalysis, Employee, Employer, PayPeriod, Income, Verifications,
    ProcessingMetadata, DocumentType, IncomeType, PayFrequency
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    return Config(
        ai=AIConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key_file=".secrets/test_key"
        ),
        processing=ProcessingConfig(
            docs_folder="test_docs",
            archive_folder="test_archive",
            max_file_size_mb=10,
            supported_formats=["pdf", "png", "jpg"]
        ),
        verification=VerificationConfig(
            max_age_months=6,
            min_consecutive_periods=3,
            require_qualified_accountant_signature=False
        ),
        fraud_detection=FraudDetectionConfig(
            confidence_threshold=0.7,
            font_consistency_check=True,
            total_validation=True,
            ocr_quality_threshold=0.8
        ),
        output=OutputConfig(
            log_level="INFO",
            json_indent=2,
            console_summary=True
        )
    )


@pytest.fixture
def sample_processing_metadata(temp_dir):
    """Create sample processing metadata."""
    return ProcessingMetadata(
        file_path=str(temp_dir / "test_document.pdf"),
        file_size_bytes=1024,
        processing_timestamp=datetime.now(),
        ocr_quality_score=0.9,
        pages_processed=1
    )


@pytest.fixture
def sample_employee():
    """Create sample employee data."""
    return Employee(
        name="John Smith",
        ni_number="AB123456C",
        employee_id="EMP001",
        confidence=0.95
    )


@pytest.fixture
def sample_employer():
    """Create sample employer data."""
    return Employer(
        name="Acme Corporation Ltd",
        address="123 Business Street, London",
        company_registration="12345678",
        confidence=0.90
    )


@pytest.fixture
def sample_pay_period():
    """Create sample pay period data."""
    return PayPeriod(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        pay_date=date(2024, 2, 5),
        frequency=PayFrequency.MONTHLY,
        confidence=0.95
    )


@pytest.fixture
def sample_income():
    """Create sample income data."""
    return [
        Income(
            type=IncomeType.SALARY,
            amount_gbp=3000.00,
            description="Basic Salary",
            confidence=0.95
        ),
        Income(
            type=IncomeType.BONUS,
            amount_gbp=500.00,
            description="Performance Bonus",
            confidence=0.85
        )
    ]


@pytest.fixture
def sample_verifications():
    """Create sample verification data."""
    return Verifications(
        recency_pass=True,
        consecutive_pass=True,
        qualified_signature_pass=None,
        total_consistency_pass=True,
        date_format_pass=True
    )


@pytest.fixture
def sample_document_analysis(sample_processing_metadata, sample_employee, 
                           sample_employer, sample_pay_period, sample_income,
                           sample_verifications):
    """Create a complete sample document analysis."""
    return DocumentAnalysis(
        document_type=DocumentType.PAYSLIP,
        employee=sample_employee,
        employer=sample_employer,
        pay_period=sample_pay_period,
        income=sample_income,
        total_gross_pay=3500.00,
        total_net_pay=2800.00,
        verifications=sample_verifications,
        fraud_signals=[],
        overall_confidence=0.92,
        processing_metadata=sample_processing_metadata,
        raw_text="Sample payslip text content"
    )


@pytest.fixture
def mock_ai_client():
    """Create a mock AI client."""
    mock_client = Mock()
    mock_client.analyze_document.return_value = """{
        "document_type": "payslip",
        "employee": {
            "name": "John Smith",
            "ni_number": "AB123456C",
            "employee_id": "EMP001",
            "confidence": 0.95
        },
        "employer": {
            "name": "Acme Corporation Ltd",
            "address": "123 Business Street, London",
            "company_registration": "12345678",
            "confidence": 0.90
        },
        "pay_period": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "pay_date": "2024-02-05",
            "frequency": "monthly",
            "confidence": 0.95
        },
        "income": [
            {
                "type": "salary",
                "amount_gbp": 3000.00,
                "description": "Basic Salary",
                "confidence": 0.95
            }
        ],
        "total_gross_pay": 3000.00,
        "total_net_pay": 2400.00,
        "fraud_signals": [],
        "overall_confidence": 0.92,
        "raw_text_summary": "Basic payslip"
    }"""
    return mock_client


@pytest.fixture
def sample_pdf_file(temp_dir):
    """Create a sample PDF file for testing."""
    pdf_path = temp_dir / "sample.pdf"
    # Create a minimal PDF-like file (not a real PDF, just for testing file operations)
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Root 1 0 R >>\n%%EOF")
    return pdf_path


@pytest.fixture
def sample_image_file(temp_dir):
    """Create a sample image file for testing."""
    from PIL import Image
    import io
    
    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='white')
    img_path = temp_dir / "sample.png"
    img.save(str(img_path))
    return img_path
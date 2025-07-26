"""Tests for document extractor functionality."""

import pytest
import json
from unittest.mock import Mock, patch
from pathlib import Path

from services.extractor import DocumentExtractor
from services.models import DocumentType


def test_extractor_init(sample_config, mock_ai_client):
    """Test DocumentExtractor initialization."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    assert extractor.config == sample_config
    assert extractor.ai_client == mock_ai_client


def test_calculate_ocr_quality(sample_config, mock_ai_client):
    """Test OCR quality calculation."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    # Good quality text
    good_text = "This is clear, readable text with proper formatting."
    quality = extractor.calculate_ocr_quality(good_text, 1024)
    assert 0.5 <= quality <= 1.0
    
    # Poor quality text with OCR errors
    poor_text = "Th1s 1s p00r qu4l1ty t3xt w1th OCR 3rr0rs |||"
    quality = extractor.calculate_ocr_quality(poor_text, 1024)
    assert quality < 0.8
    
    # Empty text
    quality = extractor.calculate_ocr_quality("", 1024)
    assert quality == 0.0


def test_parse_ai_response_valid_json(sample_config, mock_ai_client):
    """Test parsing valid AI response."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    response = """{
        "document_type": "payslip",
        "employee": {"name": "John Doe", "confidence": 0.9},
        "overall_confidence": 0.85
    }"""
    
    parsed = extractor.parse_ai_response(response)
    
    assert parsed["document_type"] == "payslip"
    assert parsed["employee"]["name"] == "John Doe"
    assert parsed["overall_confidence"] == 0.85


def test_parse_ai_response_with_markdown(sample_config, mock_ai_client):
    """Test parsing AI response wrapped in markdown."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    response = """Here's the analysis:

```json
{
    "document_type": "payslip",
    "overall_confidence": 0.85
}
```

That's the result."""
    
    parsed = extractor.parse_ai_response(response)
    
    assert parsed["document_type"] == "payslip"
    assert parsed["overall_confidence"] == 0.85


def test_parse_ai_response_invalid_json(sample_config, mock_ai_client):
    """Test parsing invalid AI response."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    response = "This is not JSON at all"
    
    with pytest.raises(ValueError):
        extractor.parse_ai_response(response)


def test_create_document_analysis(sample_config, mock_ai_client, sample_processing_metadata):
    """Test creating DocumentAnalysis from AI response."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    ai_response = {
        "document_type": "payslip",
        "employee": {
            "name": "John Smith",
            "ni_number": "AB123456C",
            "confidence": 0.95
        },
        "employer": {
            "name": "Acme Corp Ltd",
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
                "confidence": 0.95
            }
        ],
        "total_gross_pay": 3000.00,
        "total_net_pay": 2400.00,
        "fraud_signals": ["test_signal"],
        "overall_confidence": 0.92
    }
    
    text_content = "Sample payslip text"
    
    analysis = extractor.create_document_analysis(
        ai_response, sample_processing_metadata, text_content
    )
    
    assert analysis.document_type == DocumentType.PAYSLIP
    assert analysis.employee.name == "John Smith"
    assert analysis.employee.ni_number == "AB123456C"
    assert analysis.employer.name == "Acme Corp Ltd"
    assert analysis.total_gross_pay == 3000.00
    assert len(analysis.income) == 1
    assert analysis.income[0].amount_gbp == 3000.00
    assert "test_signal" in analysis.fraud_signals
    assert analysis.overall_confidence == 0.92


def test_extract_text_from_pdf(sample_config, mock_ai_client, sample_pdf_file):
    """Test PDF text extraction."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    # Mock PyPDF2 functionality
    with patch('PyPDF2.PdfReader') as mock_reader:
        mock_page = Mock()
        mock_page.extract_text.return_value = "Sample PDF text content"
        
        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_reader.return_value = mock_pdf
        
        text, pages = extractor.extract_text_from_pdf(sample_pdf_file)
        
        assert "Sample PDF text content" in text
        assert pages == 1


def test_load_image_file(sample_config, mock_ai_client, sample_image_file):
    """Test image file loading."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    image_data = extractor.load_image_file(sample_image_file)
    
    assert isinstance(image_data, bytes)
    assert len(image_data) > 0


@patch('services.extractor.DocumentExtractor.convert_pdf_to_image')
@patch('services.extractor.DocumentExtractor.extract_text_from_pdf')
def test_process_document_pdf(mock_extract_text, mock_convert_image, 
                             sample_config, mock_ai_client, sample_pdf_file, 
                             sample_processing_metadata):
    """Test processing PDF document."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    # Setup mocks
    mock_extract_text.return_value = ("Sample PDF text", 1)
    mock_convert_image.return_value = b"fake_image_data"
    
    # Mock AI response
    mock_ai_client.analyze_document.return_value = """{
        "document_type": "payslip",
        "employee": {"name": "John Doe", "confidence": 0.9},
        "employer": {"name": "Test Corp", "confidence": 0.8},
        "pay_period": {"confidence": 0.7},
        "income": [],
        "fraud_signals": [],
        "overall_confidence": 0.85
    }"""
    
    analysis = extractor.process_document(sample_pdf_file, sample_processing_metadata)
    
    assert analysis.document_type == DocumentType.PAYSLIP
    assert analysis.employee.name == "John Doe"
    assert analysis.overall_confidence == 0.85
    
    # Verify AI client was called
    mock_ai_client.analyze_document.assert_called_once()


@patch('services.extractor.DocumentExtractor.load_image_file')
def test_process_document_image(mock_load_image, sample_config, mock_ai_client, 
                               sample_image_file, sample_processing_metadata):
    """Test processing image document."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    # Setup mocks
    mock_load_image.return_value = b"fake_image_data"
    
    # Mock AI response
    mock_ai_client.analyze_document.return_value = """{
        "document_type": "payslip",
        "employee": {"name": "Jane Doe", "confidence": 0.9},
        "employer": {"name": "Image Corp", "confidence": 0.8},
        "pay_period": {"confidence": 0.7},
        "income": [],
        "fraud_signals": [],
        "overall_confidence": 0.80
    }"""
    
    analysis = extractor.process_document(sample_image_file, sample_processing_metadata)
    
    assert analysis.document_type == DocumentType.PAYSLIP
    assert analysis.employee.name == "Jane Doe"
    assert analysis.overall_confidence == 0.80
    
    # Verify AI client was called
    mock_ai_client.analyze_document.assert_called_once()


def test_process_document_error_handling(sample_config, mock_ai_client, 
                                       sample_pdf_file, sample_processing_metadata):
    """Test error handling during document processing."""
    extractor = DocumentExtractor(sample_config, mock_ai_client)
    
    # Make AI client raise an exception
    mock_ai_client.analyze_document.side_effect = Exception("AI processing failed")
    
    analysis = extractor.process_document(sample_pdf_file, sample_processing_metadata)
    
    # Should return a minimal analysis with error info
    assert analysis.document_type == DocumentType.OTHER
    assert analysis.overall_confidence == 0.0
    assert any("Processing error" in signal for signal in analysis.fraud_signals)
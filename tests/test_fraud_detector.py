"""Tests for fraud detector functionality."""

import pytest
from datetime import date

from services.fraud_detector import FraudDetector
from services.models import DocumentType


def test_fraud_detector_init(sample_config):
    """Test FraudDetector initialization."""
    detector = FraudDetector(sample_config)
    assert detector.config == sample_config


def test_analyze_text_consistency_clean_text(sample_config, sample_document_analysis):
    """Test text consistency analysis with clean text."""
    detector = FraudDetector(sample_config)
    
    sample_document_analysis.raw_text = "Clean, professional payslip text without issues."
    
    fraud_signals = detector.analyze_text_consistency(sample_document_analysis)
    assert len(fraud_signals) == 0


def test_analyze_text_consistency_suspicious_patterns(sample_config, sample_document_analysis):
    """Test text consistency analysis with suspicious patterns."""
    detector = FraudDetector(sample_config)
    
    # Text with suspicious patterns
    sample_document_analysis.raw_text = "ABC123DEF   excessive   spaces  and  l1l0O0o patterns"
    
    fraud_signals = detector.analyze_text_consistency(sample_document_analysis)
    assert len(fraud_signals) > 0
    assert any("suspicious_" in signal for signal in fraud_signals)


def test_validate_calculations_correct(sample_config, sample_document_analysis):
    """Test calculation validation with correct totals."""
    detector = FraudDetector(sample_config)
    
    # Income items sum to 3500, matches total_gross_pay
    fraud_signals = detector.validate_calculations(sample_document_analysis)
    assert "calculation_mismatch" not in fraud_signals


def test_validate_calculations_mismatch(sample_config, sample_document_analysis):
    """Test calculation validation with mismatched totals."""
    detector = FraudDetector(sample_config)
    
    # Change total to not match income sum
    sample_document_analysis.total_gross_pay = 4000.00  # Income sums to 3500
    
    fraud_signals = detector.validate_calculations(sample_document_analysis)
    assert "calculation_mismatch" in fraud_signals


def test_validate_calculations_unrealistic_amounts(sample_config, sample_document_analysis):
    """Test calculation validation with unrealistic amounts."""
    detector = FraudDetector(sample_config)
    
    # Set unrealistically high amount
    sample_document_analysis.total_gross_pay = 100000.00
    
    fraud_signals = detector.validate_calculations(sample_document_analysis)
    assert "unrealistic_high_amount" in fraud_signals


def test_validate_calculations_negative_amounts(sample_config, sample_document_analysis):
    """Test calculation validation with negative amounts."""
    detector = FraudDetector(sample_config)
    
    # Set negative total
    sample_document_analysis.total_gross_pay = -1000.00
    
    fraud_signals = detector.validate_calculations(sample_document_analysis)
    assert "negative_amount" in fraud_signals


def test_check_employer_legitimacy_valid(sample_config, sample_document_analysis):
    """Test employer legitimacy check with valid employer."""
    detector = FraudDetector(sample_config)
    
    # Valid employer name with Ltd suffix
    sample_document_analysis.employer.name = "Acme Corporation Ltd"
    
    fraud_signals = detector.check_employer_legitimacy(sample_document_analysis)
    assert "no_company_suffix" not in fraud_signals
    assert "suspicious_employer_name" not in fraud_signals


def test_check_employer_legitimacy_no_suffix(sample_config, sample_document_analysis):
    """Test employer legitimacy check with no company suffix."""
    detector = FraudDetector(sample_config)
    
    # Employer name without proper suffix
    sample_document_analysis.employer.name = "Acme Corporation"
    sample_document_analysis.document_type = DocumentType.PAYSLIP
    
    fraud_signals = detector.check_employer_legitimacy(sample_document_analysis)
    assert "no_company_suffix" in fraud_signals


def test_check_employer_legitimacy_suspicious_name(sample_config, sample_document_analysis):
    """Test employer legitimacy check with suspicious name."""
    detector = FraudDetector(sample_config)
    
    # Suspicious employer name
    sample_document_analysis.employer.name = "Cash Money Ltd"
    
    fraud_signals = detector.check_employer_legitimacy(sample_document_analysis)
    assert "suspicious_employer_name" in fraud_signals


def test_check_employer_legitimacy_single_word(sample_config, sample_document_analysis):
    """Test employer legitimacy check with single word employer."""
    detector = FraudDetector(sample_config)
    
    # Single word employer name
    sample_document_analysis.employer.name = "Bob"
    
    fraud_signals = detector.check_employer_legitimacy(sample_document_analysis)
    assert "single_word_employer" in fraud_signals


def test_analyze_date_patterns_valid(sample_config, sample_document_analysis):
    """Test date pattern analysis with valid dates."""
    detector = FraudDetector(sample_config)
    
    # Set valid dates (past dates in logical order)
    sample_document_analysis.pay_period.start_date = date(2024, 1, 1)
    sample_document_analysis.pay_period.end_date = date(2024, 1, 31)
    sample_document_analysis.pay_period.pay_date = date(2024, 2, 5)
    
    fraud_signals = detector.analyze_date_patterns(sample_document_analysis)
    assert len(fraud_signals) == 0


def test_analyze_date_patterns_future_dates(sample_config, sample_document_analysis):
    """Test date pattern analysis with future dates."""
    detector = FraudDetector(sample_config)
    
    # Set future pay date
    from datetime import date, timedelta
    future_date = date.today() + timedelta(days=30)
    sample_document_analysis.pay_period.pay_date = future_date
    
    fraud_signals = detector.analyze_date_patterns(sample_document_analysis)
    assert "future_pay_date" in fraud_signals


def test_analyze_date_patterns_invalid_order(sample_config, sample_document_analysis):
    """Test date pattern analysis with invalid date order."""
    detector = FraudDetector(sample_config)
    
    # Set start date after end date
    sample_document_analysis.pay_period.start_date = date(2024, 2, 1)
    sample_document_analysis.pay_period.end_date = date(2024, 1, 31)
    
    fraud_signals = detector.analyze_date_patterns(sample_document_analysis)
    assert "invalid_date_order" in fraud_signals


def test_check_ni_number_validity_valid(sample_config, sample_document_analysis):
    """Test NI number validation with valid number."""
    detector = FraudDetector(sample_config)
    
    sample_document_analysis.employee.ni_number = "AB123456C"
    
    fraud_signals = detector.check_ni_number_validity(sample_document_analysis)
    assert "invalid_ni_format" not in fraud_signals
    assert "fake_ni_number" not in fraud_signals


def test_check_ni_number_validity_invalid_format(sample_config, sample_document_analysis):
    """Test NI number validation with invalid format."""
    detector = FraudDetector(sample_config)
    
    sample_document_analysis.employee.ni_number = "INVALID123"
    
    fraud_signals = detector.check_ni_number_validity(sample_document_analysis)
    assert "invalid_ni_format" in fraud_signals


def test_check_ni_number_validity_fake_number(sample_config, sample_document_analysis):
    """Test NI number validation with obviously fake number."""
    detector = FraudDetector(sample_config)
    
    sample_document_analysis.employee.ni_number = "AA000000A"
    
    fraud_signals = detector.check_ni_number_validity(sample_document_analysis)
    assert "fake_ni_number" in fraud_signals


def test_detect_template_usage_no_reuse(sample_config):
    """Test template usage detection with unique documents."""
    detector = FraudDetector(sample_config)
    
    # Create two documents with different text
    analyses = []
    for i in range(2):
        analysis = sample_document_analysis.model_copy()
        analysis.raw_text = f"Unique payslip text content {i}"
        analyses.append(analysis)
    
    result = detector.detect_template_usage(analyses)
    assert result["template_reuse_detected"] == False


def test_detect_template_usage_with_reuse(sample_config):
    """Test template usage detection with similar documents."""
    detector = FraudDetector(sample_config)
    
    # Create two documents with very similar text
    similar_text = "This is a standard payslip template with minor variations"
    analyses = []
    for i in range(2):
        analysis = sample_document_analysis.model_copy()
        analysis.raw_text = similar_text
        analyses.append(analysis)
    
    result = detector.detect_template_usage(analyses)
    assert result["template_reuse_detected"] == True


def test_analyze_document(sample_config, sample_document_analysis):
    """Test comprehensive document fraud analysis."""
    detector = FraudDetector(sample_config)
    
    # Start with clean document
    original_confidence = sample_document_analysis.overall_confidence
    
    analyzed = detector.analyze_document(sample_document_analysis)
    
    # Should return the same document with fraud analysis applied
    assert analyzed == sample_document_analysis
    # Confidence should be maintained or slightly reduced
    assert analyzed.overall_confidence <= original_confidence


def test_analyze_document_with_fraud_signals(sample_config, sample_document_analysis):
    """Test document analysis with fraud indicators."""
    detector = FraudDetector(sample_config)
    
    # Add conditions that trigger fraud signals
    sample_document_analysis.total_gross_pay = 4000.00  # Doesn't match income sum
    sample_document_analysis.employer.name = "Cash Corp"  # Suspicious name
    sample_document_analysis.employee.ni_number = "INVALID"  # Invalid format
    
    original_confidence = sample_document_analysis.overall_confidence
    
    analyzed = detector.analyze_document(sample_document_analysis)
    
    # Should have multiple fraud signals
    assert len(analyzed.fraud_signals) > 0
    # Confidence should be significantly reduced
    assert analyzed.overall_confidence < original_confidence


def test_analyze_batch(sample_config):
    """Test batch fraud analysis."""
    detector = FraudDetector(sample_config)
    
    # Create batch of documents
    analyses = []
    for i in range(3):
        analysis = sample_document_analysis.model_copy()
        analysis.raw_text = f"Document {i} with unique content"
        analyses.append(analysis)
    
    analyzed_batch = detector.analyze_batch(analyses)
    
    assert len(analyzed_batch) == 3
    # Each document should have been analyzed
    for analysis in analyzed_batch:
        assert hasattr(analysis, 'fraud_signals')
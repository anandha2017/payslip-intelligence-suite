"""Tests for document verifier functionality."""

import pytest
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from services.verifier import DocumentVerifier
from services.models import DocumentType, PayFrequency


def test_verifier_init(sample_config):
    """Test DocumentVerifier initialization."""
    verifier = DocumentVerifier(sample_config)
    assert verifier.config == sample_config


def test_check_document_recency_recent(sample_config, sample_document_analysis):
    """Test recency check with recent document."""
    verifier = DocumentVerifier(sample_config)
    
    # Set pay date to last month (should pass)
    sample_document_analysis.pay_period.pay_date = date.today() - relativedelta(months=1)
    
    result = verifier.check_document_recency(sample_document_analysis)
    assert result == True


def test_check_document_recency_old(sample_config, sample_document_analysis):
    """Test recency check with old document."""
    verifier = DocumentVerifier(sample_config)
    
    # Set pay date to 12 months ago (should fail with 6 month limit)
    sample_document_analysis.pay_period.pay_date = date.today() - relativedelta(months=12)
    
    result = verifier.check_document_recency(sample_document_analysis)
    assert result == False


def test_check_document_recency_no_date(sample_config, sample_document_analysis):
    """Test recency check with no pay date."""
    verifier = DocumentVerifier(sample_config)
    
    sample_document_analysis.pay_period.pay_date = None
    
    result = verifier.check_document_recency(sample_document_analysis)
    assert result == False


def test_check_total_consistency_valid(sample_config, sample_document_analysis):
    """Test total consistency check with matching totals."""
    verifier = DocumentVerifier(sample_config)
    
    # Income items sum to 3500 (3000 + 500), matches total_gross_pay
    result = verifier.check_total_consistency(sample_document_analysis)
    assert result == True


def test_check_total_consistency_invalid(sample_config, sample_document_analysis):
    """Test total consistency check with mismatched totals."""
    verifier = DocumentVerifier(sample_config)
    
    # Change total to not match income sum
    sample_document_analysis.total_gross_pay = 4000.00  # Income sums to 3500
    
    result = verifier.check_total_consistency(sample_document_analysis)
    assert result == False


def test_check_total_consistency_no_data(sample_config, sample_document_analysis):
    """Test total consistency check with missing data."""
    verifier = DocumentVerifier(sample_config)
    
    sample_document_analysis.income = []
    
    result = verifier.check_total_consistency(sample_document_analysis)
    assert result == False


def test_check_qualified_signature(sample_config, sample_document_analysis):
    """Test qualified signature check."""
    sample_config.verification.require_qualified_accountant_signature = True
    verifier = DocumentVerifier(sample_config)
    
    # Test with signature indicators in text
    sample_document_analysis.raw_text = "Signed by John Smith, Chartered Accountant (ACA)"
    result = verifier.check_qualified_signature(sample_document_analysis)
    assert result == True
    
    # Test without signature indicators
    sample_document_analysis.raw_text = "Regular payslip text"
    result = verifier.check_qualified_signature(sample_document_analysis)
    assert result == False
    
    # Test when signature not required
    sample_config.verification.require_qualified_accountant_signature = False
    result = verifier.check_qualified_signature(sample_document_analysis)
    assert result == True


def test_consecutive_periods_valid(sample_config):
    """Test consecutive periods check with valid sequence."""
    verifier = DocumentVerifier(sample_config)
    sample_config.verification.min_consecutive_periods = 3
    
    # Create 3 consecutive monthly payslips
    analyses = []
    for i in range(3):
        analysis = sample_document_analysis.model_copy()
        analysis.employee.name = "John Smith"
        analysis.pay_period.pay_date = date(2024, i + 1, 28)  # Jan, Feb, Mar
        analysis.pay_period.frequency = PayFrequency.MONTHLY
        analyses.append(analysis)
    
    results = verifier.check_consecutive_periods(analyses)
    assert results["John Smith"] == True


def test_consecutive_periods_invalid_gaps(sample_config):
    """Test consecutive periods check with gaps."""
    verifier = DocumentVerifier(sample_config)
    sample_config.verification.min_consecutive_periods = 3
    
    # Create payslips with gaps
    analyses = []
    dates = [date(2024, 1, 28), date(2024, 3, 28), date(2024, 5, 28)]  # Skip Feb, Apr
    
    for i, pay_date in enumerate(dates):
        analysis = sample_document_analysis.model_copy()
        analysis.employee.name = "John Smith"
        analysis.pay_period.pay_date = pay_date
        analysis.pay_period.frequency = PayFrequency.MONTHLY
        analyses.append(analysis)
    
    results = verifier.check_consecutive_periods(analyses)
    assert results["John Smith"] == False


def test_consecutive_periods_insufficient_count(sample_config):
    """Test consecutive periods check with insufficient documents."""
    verifier = DocumentVerifier(sample_config)
    sample_config.verification.min_consecutive_periods = 3
    
    # Create only 2 payslips
    analyses = []
    for i in range(2):
        analysis = sample_document_analysis.model_copy()
        analysis.employee.name = "John Smith"
        analysis.pay_period.pay_date = date(2024, i + 1, 28)
        analysis.pay_period.frequency = PayFrequency.MONTHLY
        analyses.append(analysis)
    
    results = verifier.check_consecutive_periods(analyses)
    assert results["John Smith"] == False


def test_validate_income_consistency_consistent(sample_config):
    """Test income consistency validation with consistent amounts."""
    verifier = DocumentVerifier(sample_config)
    
    # Create payslips with consistent income
    analyses = []
    for i in range(3):
        analysis = sample_document_analysis.model_copy()
        analysis.employee.name = "John Smith"
        analysis.total_gross_pay = 3000.00  # Consistent amount
        analysis.pay_period.pay_date = date(2024, i + 1, 28)
        analysis.pay_period.frequency = PayFrequency.MONTHLY
        analyses.append(analysis)
    
    results = verifier.validate_income_consistency(analyses)
    
    assert results["John Smith"]["consistent"] == True
    assert len(results["John Smith"]["outliers"]) == 0


def test_validate_income_consistency_outliers(sample_config):
    """Test income consistency validation with outliers."""
    verifier = DocumentVerifier(sample_config)
    
    # Create payslips with one outlier
    analyses = []
    amounts = [3000.00, 3000.00, 5000.00]  # Third one is an outlier
    
    for i, amount in enumerate(amounts):
        analysis = sample_document_analysis.model_copy()
        analysis.employee.name = "John Smith"
        analysis.total_gross_pay = amount
        analysis.pay_period.pay_date = date(2024, i + 1, 28)
        analysis.pay_period.frequency = PayFrequency.MONTHLY
        analyses.append(analysis)
    
    results = verifier.validate_income_consistency(analyses)
    
    assert results["John Smith"]["consistent"] == False
    assert len(results["John Smith"]["outliers"]) == 1
    assert results["John Smith"]["outliers"][0]["amount"] == 5000.00


def test_verify_document(sample_config, sample_document_analysis):
    """Test single document verification."""
    verifier = DocumentVerifier(sample_config)
    
    # Set up for successful verification
    sample_document_analysis.pay_period.pay_date = date.today() - relativedelta(months=1)
    
    verified = verifier.verify_document(sample_document_analysis)
    
    assert verified.verifications.recency_pass == True
    assert verified.verifications.total_consistency_pass == True
    # Confidence should be maintained or slightly reduced
    assert verified.overall_confidence >= 0.7


def test_verify_document_with_failures(sample_config, sample_document_analysis):
    """Test single document verification with failures."""
    verifier = DocumentVerifier(sample_config)
    
    # Set up for failed verification
    sample_document_analysis.pay_period.pay_date = date.today() - relativedelta(months=12)  # Too old
    sample_document_analysis.total_gross_pay = 4000.00  # Doesn't match income sum
    
    verified = verifier.verify_document(sample_document_analysis)
    
    assert verified.verifications.recency_pass == False
    assert verified.verifications.total_consistency_pass == False
    assert "document_too_old" in verified.fraud_signals
    assert "income_total_mismatch" in verified.fraud_signals
    # Confidence should be significantly reduced
    assert verified.overall_confidence < 0.7


def test_verify_batch(sample_config):
    """Test batch verification."""
    verifier = DocumentVerifier(sample_config)
    sample_config.verification.min_consecutive_periods = 2
    
    # Create 2 consecutive valid payslips
    analyses = []
    for i in range(2):
        analysis = sample_document_analysis.model_copy()
        analysis.employee.name = "John Smith"
        analysis.pay_period.pay_date = date(2024, i + 1, 28)
        analysis.pay_period.frequency = PayFrequency.MONTHLY
        analyses.append(analysis)
    
    verified_analyses = verifier.verify_batch(analyses)
    
    assert len(verified_analyses) == 2
    for analysis in verified_analyses:
        assert analysis.verifications.consecutive_pass == True
"""Document verification and validation service."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dateutil.relativedelta import relativedelta

from .config import Config
from .models import DocumentAnalysis, PayFrequency, DocumentType

logger = logging.getLogger(__name__)


class DocumentVerifier:
    """Handles document verification and validation rules."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def check_document_recency(self, analysis: DocumentAnalysis) -> bool:
        """Check if document is within the acceptable age limit."""
        if not analysis.pay_period.pay_date:
            return False
        
        max_age = relativedelta(months=self.config.verification.max_age_months)
        cutoff_date = datetime.now().date() - max_age
        
        return analysis.pay_period.pay_date >= cutoff_date
    
    def check_consecutive_periods(self, analyses: List[DocumentAnalysis]) -> Dict[str, bool]:
        """Check if documents represent consecutive pay periods."""
        # Group by employee
        employee_docs = {}
        for analysis in analyses:
            if analysis.document_type != DocumentType.PAYSLIP:
                continue
            
            emp_key = analysis.employee.name or "unknown"
            if emp_key not in employee_docs:
                employee_docs[emp_key] = []
            employee_docs[emp_key].append(analysis)
        
        results = {}
        for emp_key, docs in employee_docs.items():
            results[emp_key] = self._check_consecutive_for_employee(docs)
        
        return results
    
    def _check_consecutive_for_employee(self, analyses: List[DocumentAnalysis]) -> bool:
        """Check consecutive periods for a single employee."""
        if len(analyses) < self.config.verification.min_consecutive_periods:
            return False
        
        # Sort by pay date
        valid_docs = [a for a in analyses if a.pay_period.pay_date]
        if len(valid_docs) < self.config.verification.min_consecutive_periods:
            return False
        
        valid_docs.sort(key=lambda x: x.pay_period.pay_date)
        
        # Check for consistent frequency
        frequency = valid_docs[0].pay_period.frequency
        if not frequency:
            return False
        
        # Check if all documents have the same frequency
        if not all(doc.pay_period.frequency == frequency for doc in valid_docs):
            return False
        
        # Calculate expected interval based on frequency
        if frequency == PayFrequency.WEEKLY:
            expected_days = 7
        elif frequency == PayFrequency.FORTNIGHTLY:
            expected_days = 14
        elif frequency == PayFrequency.MONTHLY:
            expected_days = 30  # Approximate
        else:
            return False  # Cannot validate annual frequency
        
        # Check if dates are approximately consecutive
        tolerance_days = 3  # Allow some flexibility
        
        for i in range(1, len(valid_docs)):
            current_date = valid_docs[i].pay_period.pay_date
            previous_date = valid_docs[i-1].pay_period.pay_date
            
            actual_days = (current_date - previous_date).days
            
            if abs(actual_days - expected_days) > tolerance_days:
                return False
        
        return True
    
    def check_qualified_signature(self, analysis: DocumentAnalysis) -> bool:
        """Check for qualified accountant signature (for self-employed)."""
        if not self.config.verification.require_qualified_accountant_signature:
            return True
        
        # Check if document contains indicators of qualified signature
        fraud_signals = [signal.lower() for signal in analysis.fraud_signals]
        signature_keywords = [
            'chartered accountant', 'acca', 'aca', 'fcca', 'fca',
            'certified accountant', 'qualified accountant'
        ]
        
        # Simple check - look for signature keywords in text
        if analysis.raw_text:
            text_lower = analysis.raw_text.lower()
            return any(keyword in text_lower for keyword in signature_keywords)
        
        return False
    
    def check_total_consistency(self, analysis: DocumentAnalysis) -> bool:
        """Verify that income items sum to declared totals."""
        if not analysis.income or not analysis.total_gross_pay:
            return False
        
        calculated_total = sum(item.amount_gbp for item in analysis.income)
        declared_total = analysis.total_gross_pay
        
        # Allow for small rounding differences
        tolerance = 0.01
        return abs(calculated_total - declared_total) <= tolerance
    
    def validate_income_consistency(self, analyses: List[DocumentAnalysis]) -> Dict[str, Any]:
        """Analyze income consistency across multiple documents."""
        employee_incomes = {}
        
        # Group by employee
        for analysis in analyses:
            if analysis.document_type != DocumentType.PAYSLIP:
                continue
            
            emp_key = analysis.employee.name or "unknown"
            if emp_key not in employee_incomes:
                employee_incomes[emp_key] = []
            
            if analysis.total_gross_pay:
                employee_incomes[emp_key].append({
                    'amount': analysis.total_gross_pay,
                    'date': analysis.pay_period.pay_date,
                    'frequency': analysis.pay_period.frequency
                })
        
        results = {}
        for emp_key, incomes in employee_incomes.items():
            if len(incomes) < 2:
                results[emp_key] = {
                    'consistent': True,
                    'variance': 0.0,
                    'outliers': []
                }
                continue
            
            amounts = [inc['amount'] for inc in incomes]
            mean_income = sum(amounts) / len(amounts)
            variance = sum((x - mean_income) ** 2 for x in amounts) / len(amounts)
            
            # Identify outliers (more than 20% deviation from mean)
            outliers = []
            for i, amount in enumerate(amounts):
                deviation = abs(amount - mean_income) / mean_income
                if deviation > 0.20:  # 20% threshold
                    outliers.append({
                        'index': i,
                        'amount': amount,
                        'deviation': deviation,
                        'date': incomes[i]['date']
                    })
            
            results[emp_key] = {
                'consistent': len(outliers) == 0,
                'variance': variance,
                'mean_income': mean_income,
                'outliers': outliers
            }
        
        return results
    
    def verify_document(self, analysis: DocumentAnalysis) -> DocumentAnalysis:
        """Apply verification rules to a single document."""
        # Update verification flags
        analysis.verifications.recency_pass = self.check_document_recency(analysis)
        analysis.verifications.total_consistency_pass = self.check_total_consistency(analysis)
        analysis.verifications.qualified_signature_pass = self.check_qualified_signature(analysis)
        
        # Add fraud signals based on verification failures
        if not analysis.verifications.total_consistency_pass:
            analysis.fraud_signals.append("income_total_mismatch")
        
        if not analysis.verifications.recency_pass:
            analysis.fraud_signals.append("document_too_old")
        
        # Adjust overall confidence based on verifications
        confidence_factors = [
            analysis.verifications.recency_pass,
            analysis.verifications.total_consistency_pass,
            analysis.verifications.date_format_pass
        ]
        
        if analysis.verifications.qualified_signature_pass is not None:
            confidence_factors.append(analysis.verifications.qualified_signature_pass)
        
        # Reduce confidence for each failed verification
        failed_checks = sum(1 for factor in confidence_factors if not factor)
        confidence_penalty = failed_checks * 0.15  # 15% penalty per failed check
        
        analysis.overall_confidence = max(0.0, 
            analysis.overall_confidence - confidence_penalty)
        
        return analysis
    
    def verify_batch(self, analyses: List[DocumentAnalysis]) -> List[DocumentAnalysis]:
        """Apply verification rules to a batch of documents."""
        # First, verify individual documents
        verified_analyses = [self.verify_document(analysis) for analysis in analyses]
        
        # Check consecutive periods
        consecutive_results = self.check_consecutive_periods(verified_analyses)
        
        # Update consecutive verification flags
        for analysis in verified_analyses:
            emp_key = analysis.employee.name or "unknown"
            analysis.verifications.consecutive_pass = consecutive_results.get(emp_key, False)
            
            if not analysis.verifications.consecutive_pass:
                analysis.fraud_signals.append("non_consecutive_periods")
        
        # Validate income consistency
        consistency_results = self.validate_income_consistency(verified_analyses)
        
        # Add consistency warnings to fraud signals
        for analysis in verified_analyses:
            emp_key = analysis.employee.name or "unknown"
            consistency = consistency_results.get(emp_key, {})
            
            if not consistency.get('consistent', True):
                outliers = consistency.get('outliers', [])
                if outliers:
                    analysis.fraud_signals.append("income_inconsistency_detected")
        
        logger.info(f"Verified {len(verified_analyses)} documents")
        return verified_analyses
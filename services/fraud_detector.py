"""Fraud detection service using heuristic and ML techniques."""

import re
import logging
from typing import List, Dict, Any, Set
from collections import Counter
import textdistance

from .config import Config
from .models import DocumentAnalysis, DocumentType

logger = logging.getLogger(__name__)


class FraudDetector:
    """Detects potential fraud indicators in financial documents."""
    
    def __init__(self, config: Config):
        self.config = config
        
        # Common fraud patterns
        self.suspicious_patterns = {
            'altered_fonts': [
                r'[A-Za-z]+\d+[A-Za-z]+',  # Mixed alphanumeric
                r'\d+[O0o]+\d+',           # Number-letter-number
                r'[Il1|]+[0Oo]+[Il1|]+'   # Common OCR confusion
            ],
            'suspicious_amounts': [
                r'\d+\.000+$',             # Too many zeros
                r'\d+\.\d{3,}$',          # Too many decimal places
                r'(\d+)\.\1+$'            # Repeated digits
            ],
            'formatting_issues': [
                r'\s{3,}',                # Excessive whitespace
                r'[^\w\s\.,£$€-]',        # Unusual characters
                r'#{3,}'                  # Hash symbols (OCR errors)
            ]
        }
        
        # Known legitimate employer patterns
        self.legitimate_indicators = {
            'company_suffixes': ['ltd', 'limited', 'plc', 'llp', 'partnership'],
            'tax_codes': [r'[0-9]{3,4}[LMN]', r'BR', r'NT', r'D0'],
            'ni_patterns': [r'[A-Z]{2}\d{6}[A-Z]']
        }
    
    def analyze_text_consistency(self, analysis: DocumentAnalysis) -> List[str]:
        """Analyze text for consistency issues."""
        fraud_signals = []
        
        if not analysis.raw_text:
            return fraud_signals
        
        text = analysis.raw_text
        
        # Check for suspicious patterns
        for category, patterns in self.suspicious_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    fraud_signals.append(f"suspicious_{category}")
                    break
        
        # Font consistency check
        if self.config.fraud_detection.font_consistency_check:
            fraud_signals.extend(self._check_font_consistency(text))
        
        return fraud_signals
    
    def _check_font_consistency(self, text: str) -> List[str]:
        """Check for font inconsistencies that might indicate tampering."""
        fraud_signals = []
        
        # Look for mixed character encodings
        try:
            text.encode('ascii')
        except UnicodeEncodeError:
            # Check for suspicious unicode characters
            suspicious_chars = set()
            for char in text:
                if ord(char) > 127 and char not in 'àáâãäåæçèéêëìíîïñòóôõöøùúûü':
                    suspicious_chars.add(char)
            
            if suspicious_chars:
                fraud_signals.append("suspicious_unicode_characters")
        
        # Check for inconsistent spacing patterns
        space_patterns = re.findall(r'\s+', text)
        if space_patterns:
            space_lengths = [len(pattern) for pattern in space_patterns]
            # If there's high variation in spacing, it might indicate manual editing
            if max(space_lengths) > min(space_lengths) * 3:
                fraud_signals.append("inconsistent_spacing")
        
        return fraud_signals
    
    def validate_calculations(self, analysis: DocumentAnalysis) -> List[str]:
        """Validate mathematical calculations in the document."""
        fraud_signals = []
        
        if not self.config.fraud_detection.total_validation:
            return fraud_signals
        
        # Check if totals match sum of line items
        if analysis.income and analysis.total_gross_pay:
            calculated_total = sum(item.amount_gbp for item in analysis.income)
            declared_total = analysis.total_gross_pay
            
            tolerance = 0.02  # 2 pence tolerance
            if abs(calculated_total - declared_total) > tolerance:
                fraud_signals.append("calculation_mismatch")
                logger.warning(
                    f"Calculation mismatch: calculated={calculated_total}, "
                    f"declared={declared_total}"
                )
        
        # Check for unrealistic amounts
        if analysis.total_gross_pay:
            # Flag extremely high amounts (likely errors)
            if analysis.total_gross_pay > 50000:  # £50k per pay period
                fraud_signals.append("unrealistic_high_amount")
            
            # Flag negative amounts
            if analysis.total_gross_pay < 0:
                fraud_signals.append("negative_amount")
        
        # Check individual income items
        for item in analysis.income:
            if item.amount_gbp < 0:
                fraud_signals.append("negative_income_item")
            
            # Check for suspicious round numbers
            if item.amount_gbp > 1000 and item.amount_gbp % 100 == 0:
                fraud_signals.append("suspicious_round_amount")
        
        return fraud_signals
    
    def check_employer_legitimacy(self, analysis: DocumentAnalysis) -> List[str]:
        """Check employer information for legitimacy indicators."""
        fraud_signals = []
        
        if not analysis.employer.name:
            fraud_signals.append("missing_employer_name")
            return fraud_signals
        
        employer_name = analysis.employer.name.lower()
        
        # Check for legitimate company indicators
        has_legitimate_suffix = any(
            suffix in employer_name 
            for suffix in self.legitimate_indicators['company_suffixes']
        )
        
        if not has_legitimate_suffix and analysis.document_type == DocumentType.PAYSLIP:
            fraud_signals.append("no_company_suffix")
        
        # Check for suspicious employer names
        suspicious_words = ['cash', 'money', 'payment', 'temp', 'agency']
        if any(word in employer_name for word in suspicious_words):
            fraud_signals.append("suspicious_employer_name")
        
        # Check for single word employer names (often suspicious)
        if len(employer_name.split()) == 1 and len(employer_name) < 10:
            fraud_signals.append("single_word_employer")
        
        return fraud_signals
    
    def analyze_date_patterns(self, analysis: DocumentAnalysis) -> List[str]:
        """Analyze date patterns for anomalies."""
        fraud_signals = []
        
        pay_period = analysis.pay_period
        
        # Check for future dates
        from datetime import date
        today = date.today()
        
        if pay_period.pay_date and pay_period.pay_date > today:
            fraud_signals.append("future_pay_date")
        
        if pay_period.end_date and pay_period.end_date > today:
            fraud_signals.append("future_end_date")
        
        # Check for logical date ordering
        if (pay_period.start_date and pay_period.end_date and 
            pay_period.start_date > pay_period.end_date):
            fraud_signals.append("invalid_date_order")
        
        if (pay_period.end_date and pay_period.pay_date and 
            pay_period.pay_date < pay_period.end_date):
            fraud_signals.append("pay_date_before_period_end")
        
        return fraud_signals
    
    def check_ni_number_validity(self, analysis: DocumentAnalysis) -> List[str]:
        """Validate National Insurance number format."""
        fraud_signals = []
        
        if not analysis.employee.ni_number:
            return fraud_signals
        
        ni_number = analysis.employee.ni_number.upper().replace(' ', '')
        
        # UK NI number format: 2 letters + 6 digits + 1 letter
        ni_pattern = r'^[A-Z]{2}\d{6}[A-Z]$'
        
        if not re.match(ni_pattern, ni_number):
            fraud_signals.append("invalid_ni_format")
        else:
            # Check for obviously fake NI numbers
            fake_patterns = [
                r'^AA000000A$',
                r'^[A-Z]{2}000000[A-Z]$',
                r'^[A-Z]{2}123456[A-Z]$'
            ]
            
            if any(re.match(pattern, ni_number) for pattern in fake_patterns):
                fraud_signals.append("fake_ni_number")
        
        return fraud_signals
    
    def detect_template_usage(self, analyses: List[DocumentAnalysis]) -> Dict[str, Any]:
        """Detect if multiple documents use the same template (potential fraud)."""
        if len(analyses) < 2:
            return {}
        
        # Compare raw text similarity
        text_similarities = []
        for i in range(len(analyses)):
            for j in range(i + 1, len(analyses)):
                if analyses[i].raw_text and analyses[j].raw_text:
                    similarity = textdistance.jaro_winkler(
                        analyses[i].raw_text, analyses[j].raw_text
                    )
                    text_similarities.append({
                        'doc1_index': i,
                        'doc2_index': j,
                        'similarity': similarity
                    })
        
        # Flag high similarity (potential template reuse)
        suspicious_pairs = [
            pair for pair in text_similarities 
            if pair['similarity'] > 0.85
        ]
        
        return {
            'template_reuse_detected': len(suspicious_pairs) > 0,
            'suspicious_pairs': suspicious_pairs,
            'average_similarity': sum(p['similarity'] for p in text_similarities) / len(text_similarities) if text_similarities else 0
        }
    
    def analyze_document(self, analysis: DocumentAnalysis) -> DocumentAnalysis:
        """Run fraud detection analysis on a single document."""
        fraud_signals = set(analysis.fraud_signals)  # Start with existing signals
        
        # Run various fraud detection checks
        fraud_signals.update(self.analyze_text_consistency(analysis))
        fraud_signals.update(self.validate_calculations(analysis))
        fraud_signals.update(self.check_employer_legitimacy(analysis))
        fraud_signals.update(self.analyze_date_patterns(analysis))
        fraud_signals.update(self.check_ni_number_validity(analysis))
        
        # Update analysis with new fraud signals
        analysis.fraud_signals = list(fraud_signals)
        
        # Adjust confidence based on fraud signals
        high_risk_signals = [
            'calculation_mismatch', 'invalid_date_order', 'fake_ni_number',
            'unrealistic_high_amount', 'future_pay_date'
        ]
        
        medium_risk_signals = [
            'suspicious_employer_name', 'inconsistent_spacing',
            'no_company_suffix', 'suspicious_round_amount'
        ]
        
        # Calculate fraud risk penalty
        high_risk_count = sum(1 for signal in analysis.fraud_signals if signal in high_risk_signals)
        medium_risk_count = sum(1 for signal in analysis.fraud_signals if signal in medium_risk_signals)
        
        fraud_penalty = (high_risk_count * 0.25) + (medium_risk_count * 0.10)
        analysis.overall_confidence = max(0.0, analysis.overall_confidence - fraud_penalty)
        
        # Flag document as high fraud risk if confidence drops too low
        if analysis.overall_confidence < self.config.fraud_detection.confidence_threshold:
            analysis.fraud_signals.append("high_fraud_risk")
        
        logger.info(f"Fraud analysis complete: {len(analysis.fraud_signals)} signals detected")
        return analysis
    
    def analyze_batch(self, analyses: List[DocumentAnalysis]) -> List[DocumentAnalysis]:
        """Run fraud detection on a batch of documents."""
        # Analyze individual documents
        analyzed_docs = [self.analyze_document(analysis) for analysis in analyses]
        
        # Check for template reuse across documents
        template_analysis = self.detect_template_usage(analyzed_docs)
        
        if template_analysis.get('template_reuse_detected'):
            # Add template reuse signal to suspicious documents
            for pair in template_analysis['suspicious_pairs']:
                doc1_idx = pair['doc1_index']
                doc2_idx = pair['doc2_index']
                
                analyzed_docs[doc1_idx].fraud_signals.append("potential_template_reuse")
                analyzed_docs[doc2_idx].fraud_signals.append("potential_template_reuse")
        
        logger.info(f"Fraud detection complete for {len(analyzed_docs)} documents")
        return analyzed_docs
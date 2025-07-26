"""Document extraction and processing service."""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from PIL import Image
import PyPDF2
import io

from .config import Config
from .models import DocumentAnalysis, ProcessingMetadata, DocumentType
from .ai_client import AIClient, get_analysis_prompt

logger = logging.getLogger(__name__)


class DocumentExtractor:
    """Handles document processing and data extraction."""
    
    def __init__(self, config: Config, ai_client: AIClient):
        self.config = config
        self.ai_client = ai_client
    
    def extract_text_from_pdf(self, file_path: Path) -> Tuple[str, int]:
        """Extract text content from PDF."""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_content = ""
                pages_processed = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        text_content += f"--- Page {page_num + 1} ---\n{page_text}\n\n"
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {page_num + 1}: {e}")
                
                return text_content.strip(), pages_processed
                
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            return "", 0
    
    def convert_pdf_to_image(self, file_path: Path, page_num: int = 0) -> bytes:
        """Convert PDF page to image bytes."""
        try:
            import fitz  # PyMuPDF - optional dependency for better PDF rendering
            doc = fitz.open(str(file_path))
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for better quality
            img_data = pix.tobytes("png")
            doc.close()
            return img_data
        except ImportError:
            # Fallback: use PIL to create a placeholder image
            logger.warning("PyMuPDF not available, using placeholder image")
            img = Image.new('RGB', (800, 1000), color='white')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            return img_bytes.getvalue()
        except Exception as e:
            logger.error(f"Error converting PDF to image: {e}")
            raise
    
    def load_image_file(self, file_path: Path) -> bytes:
        """Load image file as bytes."""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading image file {file_path}: {e}")
            raise
    
    def calculate_ocr_quality(self, text_content: str, file_size: int) -> float:
        """Estimate OCR quality based on text characteristics."""
        if not text_content:
            return 0.0
        
        # Simple heuristics for OCR quality
        text_length = len(text_content)
        word_count = len(text_content.split())
        
        # Check for common OCR errors
        common_errors = ['�', '|||', '###', 'l1l', 'O0o']
        error_count = sum(text_content.count(error) for error in common_errors)
        
        # Calculate quality score
        if word_count == 0:
            return 0.0
        
        error_ratio = error_count / word_count
        text_density = text_length / (file_size / 1024)  # text per KB
        
        # Normalize and combine factors
        quality = max(0.0, min(1.0, (1.0 - error_ratio) * min(1.0, text_density / 10)))
        
        return quality
    
    def parse_ai_response(self, response: str) -> dict:
        """Parse and validate AI response JSON."""
        try:
            # Extract JSON from response (handles cases where AI adds extra text)
            response = response.strip()
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                response = response[start:end].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                response = response[start:end].strip()
            
            # Find JSON object boundaries
            if not response.startswith('{'):
                start = response.find('{')
                if start != -1:
                    response = response[start:]
            
            if not response.endswith('}'):
                end = response.rfind('}')
                if end != -1:
                    response = response[:end + 1]
            
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            raise ValueError(f"Invalid JSON response from AI: {e}")
    
    def create_document_analysis(self, 
                               ai_response: dict, 
                               metadata: ProcessingMetadata, 
                               text_content: str) -> DocumentAnalysis:
        """Create DocumentAnalysis object from AI response."""
        try:
            # Parse the AI response into our data models
            from .models import (
                Employee, Employer, PayPeriod, Income, Verifications,
                DocumentType, IncomeType, PayFrequency
            )
            from datetime import datetime
            
            # Document type
            doc_type = DocumentType(ai_response.get('document_type', 'other'))
            
            # Employee info
            emp_data = ai_response.get('employee', {})
            employee = Employee(
                name=emp_data.get('name'),
                ni_number=emp_data.get('ni_number'),
                employee_id=emp_data.get('employee_id'),
                confidence=emp_data.get('confidence', 0.0)
            )
            
            # Employer info
            emp_data = ai_response.get('employer', {})
            employer = Employer(
                name=emp_data.get('name'),
                address=emp_data.get('address'),
                company_registration=emp_data.get('company_registration'),
                confidence=emp_data.get('confidence', 0.0)
            )
            
            # Pay period
            period_data = ai_response.get('pay_period', {})
            pay_period = PayPeriod(
                start_date=datetime.strptime(period_data['start_date'], '%Y-%m-%d').date() 
                    if period_data.get('start_date') else None,
                end_date=datetime.strptime(period_data['end_date'], '%Y-%m-%d').date()
                    if period_data.get('end_date') else None,
                pay_date=datetime.strptime(period_data['pay_date'], '%Y-%m-%d').date()
                    if period_data.get('pay_date') else None,
                frequency=PayFrequency(period_data['frequency'])
                    if period_data.get('frequency') else None,
                confidence=period_data.get('confidence', 0.0)
            )
            
            # Income items
            income_items = []
            for item in ai_response.get('income', []):
                income_items.append(Income(
                    type=IncomeType(item['type']),
                    amount_gbp=float(item['amount_gbp']),
                    description=item.get('description'),
                    confidence=item.get('confidence', 0.0)
                ))
            
            # Verifications (will be filled by verifier)
            verifications = Verifications(
                recency_pass=False,
                consecutive_pass=False,
                qualified_signature_pass=None,
                total_consistency_pass=False,
                date_format_pass=bool(pay_period.pay_date)
            )
            
            return DocumentAnalysis(
                document_type=doc_type,
                employee=employee,
                employer=employer,
                pay_period=pay_period,
                income=income_items,
                total_gross_pay=ai_response.get('total_gross_pay'),
                total_net_pay=ai_response.get('total_net_pay'),
                verifications=verifications,
                fraud_signals=ai_response.get('fraud_signals', []),
                overall_confidence=ai_response.get('overall_confidence', 0.0),
                processing_metadata=metadata,
                raw_text=text_content[:1000] if text_content else None  # Truncate for storage
            )
            
        except Exception as e:
            logger.error(f"Error creating DocumentAnalysis: {e}")
            raise
    
    def process_document(self, file_path: Path, metadata: ProcessingMetadata) -> DocumentAnalysis:
        """Process a single document and extract structured data."""
        logger.info(f"Processing document: {file_path}")
        
        try:
            # Determine file type and extract content
            if file_path.suffix.lower() == '.pdf':
                text_content, pages_processed = self.extract_text_from_pdf(file_path)
                image_data = self.convert_pdf_to_image(file_path)
            else:
                # Image file
                text_content = ""
                pages_processed = 1
                image_data = self.load_image_file(file_path)
            
            # Update metadata
            metadata.ocr_quality_score = self.calculate_ocr_quality(
                text_content, metadata.file_size_bytes
            )
            metadata.pages_processed = pages_processed
            
            # Get AI analysis
            prompt = get_analysis_prompt()
            ai_response_text = self.ai_client.analyze_document(
                image_data, prompt, text_content if text_content else None
            )
            
            # Parse AI response
            ai_response = self.parse_ai_response(ai_response_text)
            
            # Create structured analysis
            analysis = self.create_document_analysis(ai_response, metadata, text_content)
            
            logger.info(f"Successfully processed {file_path} as {analysis.document_type}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            # Return a minimal analysis with error info
            return DocumentAnalysis(
                document_type=DocumentType.OTHER,
                employee=Employee(confidence=0.0),
                employer=Employer(confidence=0.0),
                pay_period=PayPeriod(confidence=0.0),
                income=[],
                verifications=Verifications(
                    recency_pass=False,
                    consecutive_pass=False,
                    total_consistency_pass=False,
                    date_format_pass=False
                ),
                fraud_signals=[f"Processing error: {str(e)}"],
                overall_confidence=0.0,
                processing_metadata=metadata,
                raw_text=None
            )
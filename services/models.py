"""Data models for the Payslip Intelligence Suite."""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    PAYSLIP = "payslip"
    BANK_STATEMENT = "bank_statement"
    OTHER = "other"


class IncomeType(str, Enum):
    SALARY = "salary"
    BONUS = "bonus"
    COMMISSION = "commission"
    BENEFITS = "benefits"
    OVERTIME = "overtime"


class PayFrequency(str, Enum):
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"
    ANNUAL = "annual"


class Employee(BaseModel):
    name: Optional[str] = None
    ni_number: Optional[str] = None
    employee_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class Employer(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    company_registration: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class Income(BaseModel):
    type: IncomeType
    amount_gbp: float
    description: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class PayPeriod(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    pay_date: Optional[date] = None
    frequency: Optional[PayFrequency] = None
    confidence: float = Field(ge=0.0, le=1.0)


class Verifications(BaseModel):
    recency_pass: bool
    consecutive_pass: bool
    qualified_signature_pass: Optional[bool] = None
    total_consistency_pass: bool
    date_format_pass: bool


class ProcessingMetadata(BaseModel):
    file_path: str
    file_size_bytes: int
    processing_timestamp: datetime
    ocr_quality_score: float = Field(ge=0.0, le=1.0)
    pages_processed: int


class DocumentAnalysis(BaseModel):
    document_type: DocumentType
    employee: Employee
    employer: Employer
    pay_period: PayPeriod
    income: List[Income]
    total_gross_pay: Optional[float] = None
    total_net_pay: Optional[float] = None
    verifications: Verifications
    fraud_signals: List[str]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    processing_metadata: ProcessingMetadata
    raw_text: Optional[str] = None


class BatchResult(BaseModel):
    documents: List[DocumentAnalysis]
    summary: Dict[str, Any]
    processing_timestamp: datetime
    total_files_processed: int
    successful_extractions: int
    failed_extractions: int
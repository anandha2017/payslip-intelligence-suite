"""AI client abstraction for different providers."""

import openai
import anthropic
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import logging
import base64
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)


class AIClient(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    def analyze_document(self, 
                        image_data: bytes, 
                        prompt: str, 
                        text_content: Optional[str] = None) -> str:
        """Analyze document with AI model."""
        pass


class OpenAIClient(AIClient):
    """OpenAI client implementation."""
    
    def __init__(self, config: Config):
        self.config = config
        try:
            # Initialize with minimal parameters to avoid proxy issues
            self.client = openai.OpenAI(
                api_key=config.get_api_key(),
                timeout=60.0,
                max_retries=2
            )
        except TypeError as e:
            if "proxies" in str(e):
                # Fallback for proxy-related initialization issues
                logger.warning("Proxy parameter issue detected, trying alternative initialization")
                import httpx
                # Create a custom HTTP client without proxy parameters
                http_client = httpx.Client(timeout=60.0)
                self.client = openai.OpenAI(
                    api_key=config.get_api_key(),
                    http_client=http_client
                )
            else:
                raise
    
    def analyze_document(self, 
                        image_data: bytes, 
                        prompt: str, 
                        text_content: Optional[str] = None) -> str:
        """Analyze document using OpenAI's vision model."""
        try:
            # Encode image to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            }
                        }
                    ]
                }
            ]
            
            if text_content:
                messages[0]["content"].insert(1, {
                    "type": "text",
                    "text": f"Extracted text content:\n{text_content}"
                })
            
            response = self.client.chat.completions.create(
                model=self.config.ai.model,
                messages=messages,
                max_tokens=4000,
                temperature=0.1
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class AnthropicClient(AIClient):
    """Anthropic client implementation."""
    
    def __init__(self, config: Config):
        self.config = config
        try:
            # Initialize with minimal parameters to avoid proxy issues
            self.client = anthropic.Anthropic(
                api_key=config.get_api_key(),
                timeout=60.0,
                max_retries=2
            )
        except TypeError as e:
            if "proxies" in str(e):
                # Fallback for proxy-related initialization issues
                logger.warning("Proxy parameter issue detected, trying alternative initialization")
                import httpx
                # Create a custom HTTP client without proxy parameters
                http_client = httpx.Client(timeout=60.0)
                self.client = anthropic.Anthropic(
                    api_key=config.get_api_key(),
                    http_client=http_client
                )
            else:
                raise
    
    def analyze_document(self, 
                        image_data: bytes, 
                        prompt: str, 
                        text_content: Optional[str] = None) -> str:
        """Analyze document using Anthropic's vision model."""
        try:
            # Encode image to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
            
            if text_content:
                content.insert(1, {
                    "type": "text",
                    "text": f"Extracted text content:\n{text_content}"
                })
            
            response = self.client.messages.create(
                model=self.config.ai.model,
                max_tokens=4000,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


def create_ai_client(config: Config) -> AIClient:
    """Factory function to create appropriate AI client."""
    if config.ai.provider.lower() == "openai":
        return OpenAIClient(config)
    elif config.ai.provider.lower() == "anthropic":
        return AnthropicClient(config)
    else:
        raise ValueError(f"Unsupported AI provider: {config.ai.provider}")


def get_analysis_prompt() -> str:
    """Get the structured prompt for document analysis."""
    return """
You are a financial document analysis expert. Analyze this document and extract structured information.

Please identify:
1. Document type (payslip, bank_statement, or other)
2. Employee information (name, NI number, employee ID)
3. Employer information (name, address, company registration)
4. Pay period details (start date, end date, pay date, frequency)
5. All income items with amounts in GBP and categories (salary, bonus, commission, benefits, overtime)
6. Total gross and net pay amounts
7. Any fraud indicators (font inconsistencies, altered text, calculation errors)

Return your analysis as a JSON object with this exact structure:
{
    "document_type": "payslip|bank_statement|other",
    "employee": {
        "name": "string or null",
        "ni_number": "string or null",
        "employee_id": "string or null",
        "confidence": 0.0-1.0
    },
    "employer": {
        "name": "string or null", 
        "address": "string or null",
        "company_registration": "string or null",
        "confidence": 0.0-1.0
    },
    "pay_period": {
        "start_date": "YYYY-MM-DD or null",
        "end_date": "YYYY-MM-DD or null", 
        "pay_date": "YYYY-MM-DD or null",
        "frequency": "weekly|fortnightly|monthly|annual or null",
        "confidence": 0.0-1.0
    },
    "income": [
        {
            "type": "salary|bonus|commission|benefits|overtime",
            "amount_gbp": 0.00,
            "description": "string or null",
            "confidence": 0.0-1.0
        }
    ],
    "total_gross_pay": 0.00 or null,
    "total_net_pay": 0.00 or null,
    "fraud_signals": ["list of detected issues"],
    "overall_confidence": 0.0-1.0,
    "raw_text_summary": "brief summary of key text extracted"
}

Focus on accuracy and provide confidence scores based on text clarity and data consistency.
"""
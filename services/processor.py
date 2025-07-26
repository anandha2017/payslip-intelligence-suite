"""Main processing orchestrator for the Payslip Intelligence Suite."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TaskID

from .config import Config
from .models import BatchResult, DocumentAnalysis
from .document_loader import DocumentLoader
from .extractor import DocumentExtractor
from .verifier import DocumentVerifier
from .fraud_detector import FraudDetector
from .ai_client import create_ai_client

logger = logging.getLogger(__name__)


class PayslipProcessor:
    """Main orchestrator for document processing pipeline."""
    
    def __init__(self, config_path: str = "config.toml"):
        self.config = Config.load(config_path)
        self.console = Console()
        
        # Initialize services
        self.loader = DocumentLoader(self.config)
        self.ai_client = create_ai_client(self.config)
        self.extractor = DocumentExtractor(self.config, self.ai_client)
        self.verifier = DocumentVerifier(self.config)
        self.fraud_detector = FraudDetector(self.config)
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging based on config."""
        log_level = getattr(logging, self.config.output.log_level.upper())
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('payslip_processor.log')
            ]
        )
    
    def process_documents(self) -> BatchResult:
        """Process all documents in the incoming folder."""
        start_time = datetime.now()
        logger.info("Starting document processing batch")
        
        # Load new documents
        new_files = self.loader.scan_for_new_files()
        
        if not new_files:
            logger.info("No new documents found")
            return BatchResult(
                documents=[],
                summary={"message": "No new documents to process"},
                processing_timestamp=start_time,
                total_files_processed=0,
                successful_extractions=0,
                failed_extractions=0
            )
        
        analyses = []
        successful_count = 0
        failed_count = 0
        
        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Processing documents...", 
                total=len(new_files)
            )
            
            for file_path, metadata in new_files:
                try:
                    progress.update(task, description=f"Processing {file_path.name}")
                    
                    # Extract data
                    analysis = self.extractor.process_document(file_path, metadata)
                    analyses.append(analysis)
                    successful_count += 1
                    
                    # Archive the file
                    self.loader.archive_file(file_path)
                    
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    failed_count += 1
                
                progress.advance(task)
        
        # Apply verification rules
        if analyses:
            analyses = self.verifier.verify_batch(analyses)
            analyses = self.fraud_detector.analyze_batch(analyses)
        
        # Clean up empty directories
        self.loader.cleanup_empty_directories()
        
        # Create batch result
        batch_result = BatchResult(
            documents=analyses,
            summary=self._generate_summary(analyses),
            processing_timestamp=start_time,
            total_files_processed=len(new_files),
            successful_extractions=successful_count,
            failed_extractions=failed_count
        )
        
        logger.info(f"Batch processing complete: {successful_count} successful, {failed_count} failed")
        return batch_result
    
    def _generate_summary(self, analyses: List[DocumentAnalysis]) -> dict:
        """Generate summary statistics for the batch."""
        if not analyses:
            return {}
        
        # Document type distribution
        doc_types = {}
        for analysis in analyses:
            doc_type = analysis.document_type.value
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        
        # Confidence statistics
        confidences = [analysis.overall_confidence for analysis in analyses]
        avg_confidence = sum(confidences) / len(confidences)
        high_confidence_count = sum(1 for c in confidences if c >= 0.8)
        
        # Fraud detection summary
        total_fraud_signals = sum(len(analysis.fraud_signals) for analysis in analyses)
        high_risk_docs = sum(1 for analysis in analyses 
                           if analysis.overall_confidence < self.config.fraud_detection.confidence_threshold)
        
        # Income statistics
        total_amounts = []
        for analysis in analyses:
            if analysis.total_gross_pay:
                total_amounts.append(analysis.total_gross_pay)
        
        avg_income = sum(total_amounts) / len(total_amounts) if total_amounts else 0
        
        return {
            "document_types": doc_types,
            "confidence_stats": {
                "average": round(avg_confidence, 3),
                "high_confidence_count": high_confidence_count,
                "percentage_high_confidence": round(high_confidence_count / len(analyses) * 100, 1)
            },
            "fraud_detection": {
                "total_signals": total_fraud_signals,
                "high_risk_documents": high_risk_docs,
                "fraud_risk_percentage": round(high_risk_docs / len(analyses) * 100, 1)
            },
            "income_stats": {
                "average_gross_pay": round(avg_income, 2),
                "total_documents_with_income": len(total_amounts)
            }
        }
    
    def save_results(self, batch_result: BatchResult, output_path: str = "output"):
        """Save processing results to files."""
        output_dir = Path(output_path)
        output_dir.mkdir(exist_ok=True)
        
        timestamp = batch_result.processing_timestamp.strftime("%Y%m%d_%H%M%S")
        
        # Save individual document analyses
        for i, analysis in enumerate(batch_result.documents):
            filename = f"document_{i+1:03d}_{timestamp}.json"
            file_path = output_dir / filename
            
            with open(file_path, 'w') as f:
                json.dump(
                    analysis.model_dump(), 
                    f, 
                    indent=self.config.output.json_indent,
                    default=str
                )
        
        # Save batch summary
        summary_path = output_dir / f"batch_summary_{timestamp}.json"
        with open(summary_path, 'w') as f:
            json.dump(
                batch_result.model_dump(), 
                f, 
                indent=self.config.output.json_indent,
                default=str
            )
        
        logger.info(f"Results saved to {output_dir}")
        return output_dir
    
    def display_summary(self, batch_result: BatchResult):
        """Display processing summary to console."""
        if not self.config.output.console_summary:
            return
        
        self.console.print("\n[bold cyan]📊 Processing Summary[/bold cyan]")
        
        # Basic stats
        stats_table = Table(title="Batch Statistics")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Files Processed", str(batch_result.total_files_processed))
        stats_table.add_row("Successful Extractions", str(batch_result.successful_extractions))
        stats_table.add_row("Failed Extractions", str(batch_result.failed_extractions))
        stats_table.add_row("Processing Time", str(datetime.now() - batch_result.processing_timestamp))
        
        self.console.print(stats_table)
        
        if not batch_result.documents:
            return
        
        # Document details
        docs_table = Table(title="Document Analysis Results")
        docs_table.add_column("File", style="cyan")
        docs_table.add_column("Type", style="blue")
        docs_table.add_column("Employee", style="green")
        docs_table.add_column("Gross Pay", style="yellow")
        docs_table.add_column("Confidence", style="magenta")
        docs_table.add_column("Fraud Signals", style="red")
        
        for analysis in batch_result.documents:
            file_name = Path(analysis.processing_metadata.file_path).name
            employee_name = analysis.employee.name or "Unknown"
            gross_pay = f"£{analysis.total_gross_pay:.2f}" if analysis.total_gross_pay else "N/A"
            confidence = f"{analysis.overall_confidence:.1%}"
            fraud_count = len(analysis.fraud_signals)
            fraud_display = f"{fraud_count} signals" if fraud_count > 0 else "Clean"
            
            docs_table.add_row(
                file_name[:20] + "..." if len(file_name) > 23 else file_name,
                analysis.document_type.value,
                employee_name[:15] + "..." if len(employee_name) > 18 else employee_name,
                gross_pay,
                confidence,
                fraud_display
            )
        
        self.console.print(docs_table)
        
        # Summary statistics
        summary = batch_result.summary
        if summary.get("confidence_stats"):
            self.console.print(f"\n[bold]Average Confidence:[/bold] {summary['confidence_stats']['average']:.1%}")
            self.console.print(f"[bold]High Confidence Documents:[/bold] {summary['confidence_stats']['high_confidence_count']}")
        
        if summary.get("fraud_detection"):
            fraud_stats = summary["fraud_detection"]
            self.console.print(f"[bold red]High Risk Documents:[/bold red] {fraud_stats['high_risk_documents']}")
            self.console.print(f"[bold red]Total Fraud Signals:[/bold red] {fraud_stats['total_signals']}")
    
    def run(self) -> BatchResult:
        """Run the complete processing pipeline."""
        try:
            self.console.print("[bold green]🚀 Starting Payslip Intelligence Suite[/bold green]")
            
            # Process documents
            batch_result = self.process_documents()
            
            # Display results
            self.display_summary(batch_result)
            
            # Save results
            if batch_result.documents:
                output_dir = self.save_results(batch_result)
                self.console.print(f"\n[bold cyan]📄 Results saved to:[/bold cyan] {output_dir}")
            
            return batch_result
            
        except Exception as e:
            logger.error(f"Processing pipeline failed: {e}")
            self.console.print(f"[bold red]❌ Error:[/bold red] {e}")
            raise
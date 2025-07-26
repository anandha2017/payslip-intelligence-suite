#!/usr/bin/env python3
"""
Payslip Intelligence Suite - CLI Entry Point

A comprehensive system for processing, verifying, and analyzing payslips 
and financial documents with AI-powered extraction and fraud detection.
"""

import click
import sys
import logging
from pathlib import Path

from services.processor import PayslipProcessor
from services.config import Config

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Payslip Intelligence Suite - AI-powered document analysis."""
    pass


@cli.command()
@click.option(
    '--config', '-c', 
    default='config.toml',
    help='Path to configuration file'
)
@click.option(
    '--output', '-o',
    default='output',
    help='Output directory for results'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
def ingest(config: str, output: str, verbose: bool):
    """Ingest and process documents from the configured folder."""
    try:
        # Validate config file exists
        if not Path(config).exists():
            click.echo(f"❌ Configuration file not found: {config}", err=True)
            sys.exit(1)
        
        # Override log level if verbose
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        click.echo("🚀 Starting document ingestion...")
        
        # Initialize processor
        processor = PayslipProcessor(config)
        
        # Run processing pipeline
        batch_result = processor.run()
        
        # Save to specified output directory
        if batch_result.documents:
            processor.save_results(batch_result, output)
        
        # Exit with appropriate code
        if batch_result.failed_extractions > 0:
            click.echo(f"⚠️  Completed with {batch_result.failed_extractions} failures")
            sys.exit(1)
        else:
            click.echo("✅ Processing completed successfully")
            sys.exit(0)
            
    except KeyboardInterrupt:
        click.echo("\n❌ Processing interrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"❌ Processing failed: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option(
    '--config', '-c',
    default='config.toml',
    help='Path to configuration file'
)
def validate_config(config: str):
    """Validate configuration file and dependencies."""
    try:
        click.echo("🔍 Validating configuration...")
        
        # Load config
        cfg = Config.load(config)
        click.echo(f"✅ Configuration loaded: {config}")
        
        # Check API key
        try:
            api_key = cfg.get_api_key()
            if api_key:
                click.echo(f"✅ API key found: {cfg.ai.api_key_file}")
            else:
                click.echo(f"❌ Empty API key file: {cfg.ai.api_key_file}", err=True)
                sys.exit(1)
        except FileNotFoundError as e:
            click.echo(f"❌ API key file not found: {e}", err=True)
            sys.exit(1)
        
        # Check directories
        docs_path = Path(cfg.processing.docs_folder)
        if not docs_path.exists():
            click.echo(f"⚠️  Creating docs folder: {docs_path}")
            docs_path.mkdir(parents=True, exist_ok=True)
        else:
            click.echo(f"✅ Docs folder exists: {docs_path}")
        
        archive_path = Path(cfg.processing.archive_folder)
        if not archive_path.exists():
            click.echo(f"⚠️  Creating archive folder: {archive_path}")
            archive_path.mkdir(parents=True, exist_ok=True)
        else:
            click.echo(f"✅ Archive folder exists: {archive_path}")
        
        # Test AI client
        click.echo("🤖 Testing AI client connection...")
        from services.ai_client import create_ai_client
        
        try:
            ai_client = create_ai_client(cfg)
            click.echo(f"✅ AI client initialized: {cfg.ai.provider} ({cfg.ai.model})")
        except Exception as e:
            click.echo(f"❌ AI client failed: {e}", err=True)
            sys.exit(1)
        
        click.echo("🎉 Configuration validation successful!")
        
    except Exception as e:
        click.echo(f"❌ Configuration validation failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--config', '-c',
    default='config.toml', 
    help='Path to configuration file'
)
def status(config: str):
    """Show system status and statistics."""
    try:
        cfg = Config.load(config)
        
        click.echo("📊 System Status")
        click.echo("=" * 50)
        
        # Configuration info
        click.echo(f"Config file: {config}")
        click.echo(f"AI Provider: {cfg.ai.provider} ({cfg.ai.model})")
        click.echo(f"Docs folder: {cfg.processing.docs_folder}")
        click.echo(f"Archive folder: {cfg.processing.archive_folder}")
        
        # Check for pending documents
        docs_path = Path(cfg.processing.docs_folder)
        if docs_path.exists():
            pending_files = list(docs_path.rglob("*"))
            pending_files = [f for f in pending_files if f.is_file() and not f.name.startswith('.')]
            click.echo(f"Pending documents: {len(pending_files)}")
            
            if pending_files:
                click.echo("\nPending files:")
                for file_path in pending_files[:10]:  # Show first 10
                    click.echo(f"  • {file_path.name}")
                if len(pending_files) > 10:
                    click.echo(f"  ... and {len(pending_files) - 10} more")
        else:
            click.echo("Pending documents: 0 (folder not found)")
        
        # Check archive
        archive_path = Path(cfg.processing.archive_folder)
        if archive_path.exists():
            archive_files = list(archive_path.rglob("*"))
            archive_files = [f for f in archive_files if f.is_file()]
            click.echo(f"Archived documents: {len(archive_files)}")
        else:
            click.echo("Archived documents: 0 (folder not found)")
        
    except Exception as e:
        click.echo(f"❌ Failed to get status: {e}", err=True)
        sys.exit(1)


@cli.command()
def setup():
    """Interactive setup wizard for first-time configuration."""
    click.echo("🔧 Payslip Intelligence Suite Setup")
    click.echo("=" * 50)
    
    # Check if config already exists
    if Path("config.toml").exists():
        if not click.confirm("Configuration file already exists. Overwrite?"):
            click.echo("Setup cancelled.")
            return
    
    # AI Provider selection
    click.echo("\n1. AI Provider Configuration")
    provider = click.prompt(
        "Choose AI provider",
        type=click.Choice(['openai', 'anthropic']),
        default='openai'
    )
    
    if provider == 'openai':
        model = click.prompt("OpenAI model", default="gpt-4o-mini")
        api_key_file = ".secrets/openai_key"
    else:
        model = click.prompt("Anthropic model", default="claude-3-haiku-20240307")
        api_key_file = ".secrets/anthropic_key"
    
    # Create secrets directory
    secrets_dir = Path(".secrets")
    secrets_dir.mkdir(exist_ok=True)
    
    # Prompt for API key
    api_key = click.prompt(f"Enter your {provider.upper()} API key", hide_input=True)
    
    # Save API key
    with open(api_key_file, 'w') as f:
        f.write(api_key)
    
    click.echo(f"✅ API key saved to {api_key_file}")
    
    # Directory configuration
    click.echo("\n2. Directory Configuration")
    docs_folder = click.prompt("Documents folder", default="incoming_docs")
    archive_folder = click.prompt("Archive folder", default="archive")
    
    # Create directories
    Path(docs_folder).mkdir(exist_ok=True)
    Path(archive_folder).mkdir(exist_ok=True)
    
    # Generate config
    config_content = f"""[ai]
provider = "{provider}"
model = "{model}"
api_key_file = "{api_key_file}"

[processing]
docs_folder = "{docs_folder}"
archive_folder = "{archive_folder}"
max_file_size_mb = 50
supported_formats = ["pdf", "png", "jpg", "jpeg"]

[verification]
max_age_months = 6
min_consecutive_periods = 3
require_qualified_accountant_signature = true

[fraud_detection]
confidence_threshold = 0.7
font_consistency_check = true
total_validation = true
ocr_quality_threshold = 0.8

[output]
log_level = "INFO"
json_indent = 2
console_summary = true
"""
    
    with open("config.toml", 'w') as f:
        f.write(config_content)
    
    click.echo("✅ Configuration saved to config.toml")
    click.echo("\n🎉 Setup complete! You can now run:")
    click.echo("  python main.py ingest")


if __name__ == "__main__":
    cli()
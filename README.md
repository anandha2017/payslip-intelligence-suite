# 📄 Payslip Intelligence Suite

An AI-powered on-premises microservice for processing payslips and financial documents with advanced fraud detection and verification capabilities.

## 🚀 Quick Start (Virtual Environment Setup)

This project uses a virtual environment to keep your Mac clean and avoid polluting your system Python installation.

### 1. Initial Setup

```bash
# Clone the repository (if not already done)
# cd income-verification

# Create virtual environment and install dependencies
make dev-setup

# Run interactive configuration wizard
make setup
```

### 2. Usage

```bash
# Process documents
make run

# Check system status
make status

# Validate configuration
make validate

# Run tests
make test
```

### 3. Manual Virtual Environment Activation (Optional)

If you prefer to work directly with the virtual environment:

```bash
# Show activation command
make activate

# Activate virtual environment manually
source ./venv/bin/activate

# Now you can use python/pip directly
python main.py ingest
python main.py status

# Deactivate when done
deactivate
```

## 📁 Project Structure

```
income-verification/
├── main.py                 # CLI entry point
├── config.toml            # Configuration file
├── requirements.txt       # Python dependencies
├── Makefile              # Build and development commands
├── venv/                 # Virtual environment (auto-created)
├── services/             # Core service modules
│   ├── config.py         # Configuration management
│   ├── models.py         # Data models
│   ├── document_loader.py # File processing
│   ├── extractor.py      # AI-powered extraction
│   ├── ai_client.py      # AI provider abstraction
│   ├── verifier.py       # Document verification
│   ├── fraud_detector.py # Fraud detection
│   └── processor.py      # Main orchestrator
├── tests/                # Comprehensive test suite
├── .secrets/             # API keys (create this)
├── incoming_docs/        # Documents to process (auto-created)
├── archive/              # Processed documents (auto-created)
└── output/               # Analysis results (auto-created)
```

## 🔧 Available Make Commands

### Setup & Installation
- `make venv` - Create virtual environment
- `make install` - Install dependencies in venv
- `make dev-setup` - Complete development environment setup
- `make setup` - Interactive configuration wizard
- `make activate` - Show venv activation command

### Development
- `make test` - Run tests with coverage
- `make lint` - Code linting
- `make format` - Code formatting with Black
- `make typecheck` - Type checking with MyPy
- `make check` - All quality checks

### Execution
- `make run` - Process documents
- `make status` - System status
- `make validate` - Validate configuration

### Maintenance
- `make clean` - Clean temporary files
- `make clean-all` - Clean everything including venv
- `make requirements` - Update requirements.txt

## 🛠️ Configuration

### 1. API Key Setup

The system supports both OpenAI and Anthropic providers:

```bash
# For OpenAI (default)
echo "your-openai-api-key-here" > .secrets/openai_key

# For Anthropic (alternative)
echo "your-anthropic-api-key-here" > .secrets/anthropic_key
```

### 2. Configuration File

Edit `config.toml` to customize:

```toml
[ai]
provider = "openai"                 # or "anthropic"
model = "gpt-4o-mini"              # or "claude-3-5-sonnet-20241022"
api_key_file = ".secrets/openai_key"

[processing]
docs_folder = "incoming_docs"
archive_folder = "archive"
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
```

## 🔍 Features

### Document Processing
- ✅ Multi-format support (PDF, PNG, JPG, JPEG)
- ✅ Automatic deduplication
- ✅ OCR quality assessment
- ✅ Batch processing with progress tracking
- ✅ Date-based archiving

### AI-Powered Analysis
- ✅ Document classification (payslip, bank statement, other)
- ✅ Structured data extraction
- ✅ Employee and employer information
- ✅ Income categorization (salary, bonus, commission, benefits)
- ✅ Confidence scoring per field

### Verification Engine
- ✅ Document recency validation
- ✅ Consecutive period checking
- ✅ Qualified accountant signature verification
- ✅ Mathematical consistency validation

### Fraud Detection
- ✅ Text consistency analysis
- ✅ Font inconsistency detection
- ✅ Calculation validation
- ✅ Employer legitimacy checks
- ✅ Date pattern anomalies
- ✅ NI number format validation
- ✅ Template reuse detection

## 📊 Output Format

Results are saved as JSON files with this structure:

```json
{
  "document_type": "payslip",
  "employee": {
    "name": "John Smith",
    "ni_number": "AB123456C",
    "confidence": 0.95
  },
  "employer": {
    "name": "Acme Corporation Ltd",
    "confidence": 0.90
  },
  "income": [
    {
      "type": "salary",
      "amount_gbp": 3000.00,
      "confidence": 0.95
    }
  ],
  "verifications": {
    "recency_pass": true,
    "consecutive_pass": true,
    "total_consistency_pass": true
  },
  "fraud_signals": [],
  "overall_confidence": 0.92
}
```

## 🧪 Testing

The project includes comprehensive test coverage:

```bash
# Run all tests
make test

# Run specific test file
source ./venv/bin/activate
pytest tests/test_extractor.py -v

# Run with coverage report
make test
# Open htmlcov/index.html for detailed coverage
```

## 🔒 Security

- ✅ API keys stored outside source control
- ✅ No secrets in logs or output
- ✅ Secure file handling
- ✅ Input validation and sanitization
- ✅ Virtual environment isolation

## 🐛 Troubleshooting

### Virtual Environment Issues
```bash
# If venv gets corrupted, rebuild it
make clean-all
make dev-setup
```

### Missing Dependencies
```bash
# Reinstall all dependencies
make install
```

### Permission Issues
```bash
# Ensure proper permissions on secrets
chmod 600 .secrets/*
```

### API Key Issues
```bash
# Validate your configuration
make validate
```

## 📝 Development

### Adding New Features
1. Create feature branch
2. Add code in appropriate service module
3. Add comprehensive tests
4. Run quality checks: `make check`
5. Update documentation

### Code Style
- Black formatting (100 char line length)
- Flake8 linting
- MyPy type checking
- Comprehensive docstrings

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Set up development environment: `make dev-setup`
4. Make changes and add tests
5. Run quality checks: `make check`
6. Commit and push changes
7. Create pull request

## 📄 License

This project is designed for defensive security use only. Commercial use requires appropriate licensing.

---

**Note**: This system uses virtual environments to keep your Mac clean. All Python dependencies are installed in `./venv/` and won't affect your system Python installation.
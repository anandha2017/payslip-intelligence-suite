"""Tests for document loader functionality."""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from services.document_loader import DocumentLoader


def test_document_loader_init(sample_config, temp_dir):
    """Test DocumentLoader initialization."""
    sample_config.processing.docs_folder = str(temp_dir / "docs")
    sample_config.processing.archive_folder = str(temp_dir / "archive")
    
    loader = DocumentLoader(sample_config)
    
    assert loader.docs_folder == Path(temp_dir / "docs")
    assert loader.archive_folder == Path(temp_dir / "archive")
    assert loader.docs_folder.exists()
    assert loader.archive_folder.exists()


def test_get_file_hash(sample_config, temp_dir):
    """Test file hash generation."""
    sample_config.processing.docs_folder = str(temp_dir / "docs")
    sample_config.processing.archive_folder = str(temp_dir / "archive")
    
    loader = DocumentLoader(sample_config)
    
    # Create a test file
    test_file = temp_dir / "test.txt"
    test_file.write_text("Hello, World!")
    
    hash1 = loader.get_file_hash(test_file)
    hash2 = loader.get_file_hash(test_file)
    
    assert hash1 == hash2
    assert len(hash1) == 32  # MD5 hash length


def test_is_supported_format(sample_config, temp_dir):
    """Test file format validation."""
    sample_config.processing.docs_folder = str(temp_dir / "docs")
    sample_config.processing.archive_folder = str(temp_dir / "archive")
    sample_config.processing.supported_formats = ["pdf", "png", "jpg"]
    
    loader = DocumentLoader(sample_config)
    
    # Create test files
    pdf_file = temp_dir / "test.pdf"
    png_file = temp_dir / "test.png"
    txt_file = temp_dir / "test.txt"
    
    pdf_file.write_bytes(b"%PDF-1.4")
    png_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    txt_file.write_text("text content")
    
    with patch('magic.from_file') as mock_magic:
        mock_magic.side_effect = lambda path, mime: {
            str(pdf_file): 'application/pdf',
            str(png_file): 'image/png',
            str(txt_file): 'text/plain'
        }[path]
        
        assert loader.is_supported_format(pdf_file) == True
        assert loader.is_supported_format(png_file) == True
        assert loader.is_supported_format(txt_file) == False


def test_is_valid_file_size(sample_config, temp_dir):
    """Test file size validation."""
    sample_config.processing.docs_folder = str(temp_dir / "docs")
    sample_config.processing.archive_folder = str(temp_dir / "archive")
    sample_config.processing.max_file_size_mb = 1  # 1MB limit
    
    loader = DocumentLoader(sample_config)
    
    # Create files of different sizes
    small_file = temp_dir / "small.txt"
    small_file.write_text("small content")
    
    large_file = temp_dir / "large.txt"
    large_file.write_text("x" * (2 * 1024 * 1024))  # 2MB
    
    assert loader.is_valid_file_size(small_file) == True
    assert loader.is_valid_file_size(large_file) == False


def test_scan_for_new_files(sample_config, temp_dir):
    """Test scanning for new files."""
    docs_dir = temp_dir / "docs"
    docs_dir.mkdir()
    
    sample_config.processing.docs_folder = str(docs_dir)
    sample_config.processing.archive_folder = str(temp_dir / "archive")
    sample_config.processing.supported_formats = ["pdf", "png"]
    
    loader = DocumentLoader(sample_config)
    
    # Create test files
    pdf_file = docs_dir / "test.pdf"
    png_file = docs_dir / "test.png"
    txt_file = docs_dir / "test.txt"
    hidden_file = docs_dir / ".hidden.pdf"
    
    pdf_file.write_bytes(b"%PDF-1.4")
    png_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    txt_file.write_text("text")
    hidden_file.write_bytes(b"%PDF-1.4")
    
    with patch('magic.from_file') as mock_magic:
        mock_magic.side_effect = lambda path, mime: {
            str(pdf_file): 'application/pdf',
            str(png_file): 'image/png',
            str(txt_file): 'text/plain'
        }.get(path, 'application/octet-stream')
        
        new_files = loader.scan_for_new_files()
    
    # Should find PDF and PNG, but not TXT or hidden file
    file_paths = [path for path, metadata in new_files]
    assert len(file_paths) == 2
    assert pdf_file in file_paths
    assert png_file in file_paths
    assert txt_file not in file_paths
    assert hidden_file not in file_paths


def test_archive_file(sample_config, temp_dir):
    """Test file archiving."""
    docs_dir = temp_dir / "docs"
    archive_dir = temp_dir / "archive"
    docs_dir.mkdir()
    
    sample_config.processing.docs_folder = str(docs_dir)
    sample_config.processing.archive_folder = str(archive_dir)
    
    loader = DocumentLoader(sample_config)
    
    # Create test file
    test_file = docs_dir / "test.pdf"
    test_file.write_text("test content")
    
    archive_path = loader.archive_file(test_file)
    
    assert not test_file.exists()  # Original file moved
    assert archive_path.exists()   # Archive file exists
    assert archive_path.read_text() == "test content"
    
    # Check archive structure (YYYY-MM format)
    from datetime import datetime
    now = datetime.now()
    expected_subdir = f"{now.year:04d}-{now.month:02d}"
    assert expected_subdir in str(archive_path)


def test_archive_file_collision(sample_config, temp_dir):
    """Test handling of filename collisions during archiving."""
    docs_dir = temp_dir / "docs"
    archive_dir = temp_dir / "archive"
    docs_dir.mkdir()
    
    sample_config.processing.docs_folder = str(docs_dir)
    sample_config.processing.archive_folder = str(archive_dir)
    
    loader = DocumentLoader(sample_config)
    
    # Create two files with same name
    test_file1 = docs_dir / "test.pdf"
    test_file2 = docs_dir / "test2.pdf"
    test_file1.write_text("content 1")
    test_file2.write_text("content 2")
    
    # Archive first file
    archive_path1 = loader.archive_file(test_file1)
    
    # Rename second file to match first
    test_file2.rename(docs_dir / "test.pdf")
    
    # Archive second file (should get different name)
    archive_path2 = loader.archive_file(docs_dir / "test.pdf")
    
    assert archive_path1 != archive_path2
    assert archive_path1.exists()
    assert archive_path2.exists()
    assert archive_path1.read_text() == "content 1"
    assert archive_path2.read_text() == "content 2"
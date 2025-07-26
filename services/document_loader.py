"""Document loading and file management."""

import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Set, Tuple
import magic
import logging

from .config import Config
from .models import ProcessingMetadata

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Handles document loading, deduplication, and archiving."""
    
    def __init__(self, config: Config):
        self.config = config
        self.docs_folder = Path(config.processing.docs_folder)
        self.archive_folder = Path(config.processing.archive_folder)
        self.processed_hashes: Set[str] = set()
        
        # Create directories if they don't exist
        self.docs_folder.mkdir(exist_ok=True)
        self.archive_folder.mkdir(exist_ok=True)
    
    def get_file_hash(self, file_path: Path) -> str:
        """Generate MD5 hash of file contents."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported."""
        try:
            mime_type = magic.from_file(str(file_path), mime=True)
            extension = file_path.suffix.lower().lstrip('.')
            
            # Check by extension first
            if extension in self.config.processing.supported_formats:
                return True
            
            # Check by MIME type
            supported_mimes = {
                'application/pdf',
                'image/png',
                'image/jpeg',
                'image/jpg'
            }
            return mime_type in supported_mimes
            
        except Exception as e:
            logger.warning(f"Could not determine file type for {file_path}: {e}")
            return False
    
    def is_valid_file_size(self, file_path: Path) -> bool:
        """Check if file size is within limits."""
        size_mb = file_path.stat().st_size / (1024 * 1024)
        return size_mb <= self.config.processing.max_file_size_mb
    
    def scan_for_new_files(self) -> List[Tuple[Path, ProcessingMetadata]]:
        """Scan docs folder for new, valid files."""
        new_files = []
        
        for file_path in self.docs_folder.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Skip hidden files
            if file_path.name.startswith('.'):
                continue
            
            # Check if supported format
            if not self.is_supported_format(file_path):
                logger.info(f"Skipping unsupported file: {file_path}")
                continue
            
            # Check file size
            if not self.is_valid_file_size(file_path):
                logger.warning(f"File too large, skipping: {file_path}")
                continue
            
            # Check for duplicates
            file_hash = self.get_file_hash(file_path)
            if file_hash in self.processed_hashes:
                logger.info(f"Duplicate file detected, skipping: {file_path}")
                continue
            
            # Create processing metadata
            metadata = ProcessingMetadata(
                file_path=str(file_path),
                file_size_bytes=file_path.stat().st_size,
                processing_timestamp=datetime.now(),
                ocr_quality_score=0.0,  # Will be set during processing
                pages_processed=0  # Will be set during processing
            )
            
            new_files.append((file_path, metadata))
            self.processed_hashes.add(file_hash)
        
        logger.info(f"Found {len(new_files)} new files to process")
        return new_files
    
    def archive_file(self, file_path: Path) -> Path:
        """Move processed file to archive folder organized by year-month."""
        now = datetime.now()
        archive_subdir = self.archive_folder / f"{now.year:04d}-{now.month:02d}"
        archive_subdir.mkdir(exist_ok=True)
        
        # Generate unique filename if collision
        archive_path = archive_subdir / file_path.name
        counter = 1
        while archive_path.exists():
            stem = archive_path.stem
            suffix = archive_path.suffix
            archive_path = archive_subdir / f"{stem}_{counter}{suffix}"
            counter += 1
        
        shutil.move(str(file_path), str(archive_path))
        logger.info(f"Archived {file_path} to {archive_path}")
        return archive_path
    
    def cleanup_empty_directories(self):
        """Remove empty directories from docs folder."""
        for root, dirs, files in os.walk(self.docs_folder, topdown=False):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                try:
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        logger.debug(f"Removed empty directory: {dir_path}")
                except OSError:
                    pass  # Directory not empty or permission denied
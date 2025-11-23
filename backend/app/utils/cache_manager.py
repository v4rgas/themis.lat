"""
Cache Manager - Unified caching system for OCR results, HTML pages, and documents
"""
import os
import json
import hashlib
import tempfile
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path


class CacheManager:
    """Manages caching for OCR results, HTML pages, and documents"""

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize cache manager

        Args:
            base_dir: Base directory for cache. Defaults to /tmp/mercado_publico_cache/
        """
        if base_dir is None:
            base_dir = os.path.join(tempfile.gettempdir(), "mercado_publico_cache")

        self.base_dir = Path(base_dir)
        self.ocr_dir = self.base_dir / "ocr"
        self.html_dir = self.base_dir / "html"
        self.docs_dir = self.base_dir / "docs"

        # Create directories if they don't exist
        self.ocr_dir.mkdir(parents=True, exist_ok=True)
        self.html_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def _get_url_hash(self, url: str) -> str:
        """Generate hash for URL to use as cache key"""
        return hashlib.md5(url.encode()).hexdigest()

    # OCR Cache Methods
    def get_ocr_result(self, tender_id: str, row_id: int, page_num: int) -> Optional[str]:
        """
        Get cached OCR result for a specific page

        Args:
            tender_id: Tender ID
            row_id: Row ID
            page_num: Page number (1-indexed)

        Returns:
            Cached text if available, None otherwise
        """
        cache_file = self.ocr_dir / f"{tender_id}_{row_id}_page_{page_num}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('text')
        except (json.JSONDecodeError, IOError):
            return None

    def set_ocr_result(self, tender_id: str, row_id: int, page_num: int, text: str):
        """
        Cache OCR result for a specific page

        Args:
            tender_id: Tender ID
            row_id: Row ID
            page_num: Page number (1-indexed)
            text: Extracted text
        """
        cache_file = self.ocr_dir / f"{tender_id}_{row_id}_page_{page_num}.json"

        data = {
            'text': text,
            'cached_at': datetime.utcnow().isoformat(),
            'tender_id': tender_id,
            'row_id': row_id,
            'page_num': page_num
        }

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_ocr_results_range(
        self, tender_id: str, row_id: int, start_page: int, end_page: int
    ) -> Dict[int, str]:
        """
        Get cached OCR results for a range of pages

        Args:
            tender_id: Tender ID
            row_id: Row ID
            start_page: Start page (1-indexed, inclusive)
            end_page: End page (1-indexed, inclusive)

        Returns:
            Dictionary mapping page numbers to cached text
            Only includes pages that are cached
        """
        results = {}
        for page_num in range(start_page, end_page + 1):
            text = self.get_ocr_result(tender_id, row_id, page_num)
            if text is not None:
                results[page_num] = text
        return results

    def set_ocr_results_range(
        self, tender_id: str, row_id: int, results: Dict[int, str]
    ):
        """
        Cache OCR results for multiple pages

        Args:
            tender_id: Tender ID
            row_id: Row ID
            results: Dictionary mapping page numbers to extracted text
        """
        for page_num, text in results.items():
            self.set_ocr_result(tender_id, row_id, page_num, text)

    # HTML Cache Methods
    def get_html(self, url: str, max_age_seconds: int = 3600) -> Optional[str]:
        """
        Get cached HTML for a URL

        Args:
            url: URL to fetch
            max_age_seconds: Maximum age of cache in seconds (default: 1 hour)

        Returns:
            Cached HTML if available and not expired, None otherwise
        """
        url_hash = self._get_url_hash(url)
        cache_file = self.html_dir / f"{url_hash}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check if cache is expired
            cached_at = datetime.fromisoformat(data['cached_at'])
            age = (datetime.utcnow() - cached_at).total_seconds()

            if age > max_age_seconds:
                # Cache expired
                cache_file.unlink()
                return None

            return data.get('html')
        except (json.JSONDecodeError, IOError, KeyError, ValueError):
            return None

    def set_html(self, url: str, html: str):
        """
        Cache HTML for a URL

        Args:
            url: URL
            html: HTML content
        """
        url_hash = self._get_url_hash(url)
        cache_file = self.html_dir / f"{url_hash}.json"

        data = {
            'html': html,
            'url': url,
            'cached_at': datetime.utcnow().isoformat()
        }

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    # Document Cache Methods
    def get_document(self, tender_id: str, row_id: int) -> Optional[tuple[bytes, str]]:
        """
        Get cached document file

        Args:
            tender_id: Tender ID
            row_id: Row ID

        Returns:
            Tuple of (file_content, extension) if cached, None otherwise
        """
        # Try common extensions
        common_extensions = [".pdf", ".docx", ".doc"]

        for ext in common_extensions:
            cache_file = self.docs_dir / f"{tender_id}_{row_id}{ext}"
            if cache_file.exists():
                try:
                    with open(cache_file, 'rb') as f:
                        return (f.read(), ext)
                except IOError:
                    continue

        return None

    def set_document(self, tender_id: str, row_id: int, content: bytes, extension: str):
        """
        Cache document file

        Args:
            tender_id: Tender ID
            row_id: Row ID
            content: File content
            extension: File extension (e.g., '.pdf', '.docx')
        """
        if not extension.startswith('.'):
            extension = f'.{extension}'

        cache_file = self.docs_dir / f"{tender_id}_{row_id}{extension}"

        with open(cache_file, 'wb') as f:
            f.write(content)

    # Cache Management Methods
    def cleanup_old_cache(self, max_age_hours: int = 24):
        """
        Remove cache files older than specified age

        Args:
            max_age_hours: Maximum age in hours
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        for directory in [self.ocr_dir, self.html_dir, self.docs_dir]:
            for file_path in directory.glob("*"):
                if file_path.is_file():
                    # Check file modification time
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        try:
                            file_path.unlink()
                        except OSError:
                            pass

    def clear_cache_for_tender(self, tender_id: str):
        """
        Clear all cached data for a specific tender

        Args:
            tender_id: Tender ID to clear cache for
        """
        # Clear OCR cache
        for file_path in self.ocr_dir.glob(f"{tender_id}_*"):
            try:
                file_path.unlink()
            except OSError:
                pass

        # Clear document cache
        for file_path in self.docs_dir.glob(f"{tender_id}_*"):
            try:
                file_path.unlink()
            except OSError:
                pass

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about cache usage

        Returns:
            Dictionary with cache statistics
        """
        def count_files(directory: Path) -> int:
            return len(list(directory.glob("*")))

        def get_size(directory: Path) -> int:
            return sum(f.stat().st_size for f in directory.glob("*") if f.is_file())

        return {
            'ocr_files': count_files(self.ocr_dir),
            'ocr_size_mb': get_size(self.ocr_dir) / (1024 * 1024),
            'html_files': count_files(self.html_dir),
            'html_size_mb': get_size(self.html_dir) / (1024 * 1024),
            'docs_files': count_files(self.docs_dir),
            'docs_size_mb': get_size(self.docs_dir) / (1024 * 1024),
        }


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get or create global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

import base64
import os
import tempfile
import time
from pydantic import BaseModel, Field
from langchain.tools import tool
import requests
from bs4 import BeautifulSoup
from mistralai import Mistral
from mistralai.models import SDKError
from app.tools.read_award_result import extract_qs_from_award_page, fetch_award_modal_html, download_award_attachment_by_row_id
from app.config import settings
from app.utils.document_reader import (
    detect_file_type,
    get_file_extension_from_mime,
    extract_text_locally
)
from app.utils.cache_manager import get_cache_manager

class ReadAwardAttachmentInput(BaseModel):
    id: str = Field(
        description="The tender/acquisition ID from Mercado Público"
    )
    row_id: int = Field(
        description="The row_id of the attachment from the attachments list (0-indexed)"
    )
    start_page: int = Field(
        description="Starting page number (1-indexed). REQUIRED - you must specify which page to start reading from"
    )
    end_page: int = Field(
        description="Ending page number (1-indexed, inclusive). REQUIRED - you must specify which page to end reading at"
    )


@tool(args_schema=ReadAwardAttachmentInput)
def read_award_result_attachment_doc(id: str, row_id: int, start_page: int, end_page: int) -> dict:
    """Extract text from award result attachment (PDF/DOCX) using OCR or local extraction. ALWAYS preview (pages 1-2) before reading more.

    Args:
        id: Tender/acquisition ID from Mercado Público (e.g., "4074-24-LE19")
        row_id: Attachment ID from read_award_result attachments list (0-indexed)
        start_page: Start page (1-indexed, REQUIRED for PDFs, ignored for DOCX)
        end_page: End page (1-indexed inclusive, REQUIRED for PDFs, ignored for DOCX)

    Returns:
        dict: {text, total_pages, pages_read, file_size, success, error?}
    """
    try:
        temp_dir = tempfile.gettempdir()
        temp_subdir = os.path.join(temp_dir, "mercado_publico_award_attachments")
        os.makedirs(temp_subdir, exist_ok=True)
        
        # Try to find cached file with common extensions
        common_extensions = [".pdf", ".docx", ".doc"]
        cached = False
        file_content = None
        file_extension = None
        
        for ext in common_extensions:
            cache_filename = f"{id}_{row_id}{ext}"
            cache_path = os.path.join(temp_subdir, cache_filename)
            if os.path.exists(cache_path):
                cached = True
                with open(cache_path, 'rb') as f:
                    file_content = f.read()
                file_extension = ext
                break
        
        # If not cached, download and detect type
        if file_content is None:
            BASE_URL = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=<ID>"
            url = BASE_URL.replace("<ID>", id)
            
            response = requests.get(url, timeout=30.0)
            response.raise_for_status()
            main_html = response.text
            
            qs = extract_qs_from_award_page(main_html)
            modal_html = fetch_award_modal_html(qs)
            
            soup = BeautifulSoup(modal_html, 'html.parser')
            
            file_content = download_award_attachment_by_row_id(qs, soup, row_id)
            
            # Detect file type
            try:
                mime_type = detect_file_type(file_content)
                file_extension = get_file_extension_from_mime(mime_type)
            except Exception as e:
                # Fallback to PDF if detection fails
                print(f"Warning: Could not detect file type, defaulting to PDF: {e}")
                mime_type = "application/pdf"
                file_extension = ".pdf"
            
            # Save to cache with correct extension
            cache_filename = f"{id}_{row_id}{file_extension}"
            cache_path = os.path.join(temp_subdir, cache_filename)
            with open(cache_path, 'wb') as f:
                f.write(file_content)
        else:
            # Detect type from cached file
            try:
                mime_type = detect_file_type(file_content)
            except Exception as e:
                print(f"Warning: Could not detect file type from cache, defaulting to PDF: {e}")
                mime_type = "application/pdf"
        
        file_size = len(file_content)
        
        # Try local extraction for DOCX files
        if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            local_result = extract_text_locally(file_content, mime_type)
            
            if local_result["success"]:
                text = local_result["text"]
                # Check if text is sufficient (>= 100 chars)
                if len(text) >= 100:
                    # Return success for DOCX
                    return {
                        "text": text,
                        "total_pages": 1,  # DOCX doesn't have pages, use 1
                        "pages_read": [1],  # DOCX doesn't have pages
                        "file_size": file_size,
                        "success": True,
                        "cached": cached
                    }
                else:
                    # Text too short, return error (don't use Mistral for DOCX)
                    return {
                        "text": text,
                        "total_pages": 1,
                        "pages_read": [1],
                        "file_size": file_size,
                        "success": False,
                        "error": f"Extracted text too short ({len(text)} chars, minimum 100). Document may be empty or corrupted.",
                        "cached": cached
                    }
            else:
                # Local extraction failed
                return {
                    "text": None,
                    "total_pages": 0,
                    "pages_read": [],
                    "file_size": file_size,
                    "success": False,
                    "error": local_result.get("error", "Failed to extract text from DOCX"),
                    "cached": cached
                }
        
        # For PDFs and images, use Mistral OCR
        api_key = settings.mistral_api_key
        if not api_key:
            return {
                "text": None,
                "total_pages": 0,
                "pages_read": [],
                "file_size": file_size,
                "success": False,
                "error": "MISTRAL_API_KEY environment variable not set"
            }

        # Get cache manager
        cache = get_cache_manager()

        # Check which pages are already cached
        cached_pages = cache.get_ocr_results_range(id, row_id, start_page, end_page)

        # Determine which pages need to be OCR'd
        requested_pages = set(range(start_page, end_page + 1))
        pages_in_cache = set(cached_pages.keys())
        pages_to_ocr = requested_pages - pages_in_cache

        # If all pages are cached, return them immediately
        if not pages_to_ocr:
            extracted_text = []
            pages_read = []
            for page_num in sorted(requested_pages):
                text = cached_pages[page_num]
                extracted_text.append(f"--- Page {page_num} ---\n{text}")
                pages_read.append(page_num)

            combined_text = "\n\n".join(extracted_text)
            print(f"[CACHE HIT] OCR: award_{id}_{row_id} pages {start_page}-{end_page} - all {len(requested_pages)} pages from cache")
            return {
                "text": combined_text,
                "total_pages": max(requested_pages),  # Best estimate from cache
                "pages_read": pages_read,
                "file_size": file_size,
                "success": True,
                "cached": True,
                "ocr_cached": True
            }

        # Initialize Mistral client for pages that need OCR
        client = Mistral(api_key=api_key)

        # Encode document for OCR (only if needed)
        base64_pdf = base64.b64encode(file_content).decode('utf-8')

        # Build pages array for Mistral API (only uncached pages)
        # Convert from 1-indexed to 0-indexed for Mistral API
        pages_to_process = [p - 1 for p in sorted(pages_to_ocr)]

        ocr_params = {
            "model": "mistral-ocr-latest",
            "document": {
                "type": "document_url",
                "document_url": f"data:{mime_type};base64,{base64_pdf}"
            },
            "include_image_base64": False
        }

        ocr_params["pages"] = pages_to_process

        max_retries = 5
        base_delay = 1.0
        ocr_response = None
        
        for attempt in range(max_retries):
            try:
                ocr_response = client.ocr.process(**ocr_params)
                break
            except SDKError as e:
                http_res = e.args[1] if len(e.args) > 1 else None
                if http_res and hasattr(http_res, 'status_code') and http_res.status_code == 429:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"Rate limited, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(delay)
                        continue
                    else:
                        raise
                else:
                    raise
        
        if ocr_response is None:
            raise Exception("Failed to get OCR response after retries")

        # Extract text from OCR response and cache it
        newly_extracted = {}
        for page in ocr_response.pages:
            page_num = page.index + 1  # Convert to 1-indexed
            markdown_text = page.markdown

            if markdown_text:
                newly_extracted[page_num] = markdown_text
                # Cache this page's OCR result
                cache.set_ocr_result(id, row_id, page_num, markdown_text)

        # Log cache statistics
        if len(cached_pages) > 0 and len(newly_extracted) > 0:
            print(f"[CACHE PARTIAL] OCR: award_{id}_{row_id} - {len(cached_pages)} from cache, {len(newly_extracted)} new from API")
        elif len(newly_extracted) > 0:
            print(f"[CACHE MISS] OCR: award_{id}_{row_id} pages {start_page}-{end_page} - {len(newly_extracted)} pages from API (cached for future use)")

        # Combine cached pages and newly extracted pages
        all_pages = {**cached_pages, **newly_extracted}

        extracted_text = []
        pages_read = []
        for page_num in sorted(requested_pages):
            if page_num in all_pages:
                text = all_pages[page_num]
                extracted_text.append(f"--- Page {page_num} ---\n{text}")
                pages_read.append(page_num)

        combined_text = "\n\n".join(extracted_text)

        if hasattr(ocr_response, 'usage_info') and hasattr(ocr_response.usage_info, 'num_pages'):
            total_pages = ocr_response.usage_info.num_pages
        else:
            total_pages = len(ocr_response.pages)

        return {
            "text": combined_text,
            "total_pages": total_pages,
            "pages_read": pages_read,
            "file_size": file_size,
            "success": True,
            "cached": cached,
            "ocr_cached": len(cached_pages) > 0,
            "ocr_cache_hits": len(cached_pages),
            "ocr_new_pages": len(newly_extracted)
        }

    except Exception as e:
        import traceback
        print(f"Error reading award result attachment doc: {e}")
        traceback.print_exc()
        return {
            "text": None,
            "total_pages": 0,
            "pages_read": [],
            "file_size": 0,
            "success": False,
            "error": str(e)
        }

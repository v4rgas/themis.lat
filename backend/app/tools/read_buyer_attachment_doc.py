import base64
import os
from typing import Optional
from pydantic import BaseModel, Field
from langchain.tools import tool

from mistralai import Mistral

from app.tools.read_supplier_attachments import (
    download_buyer_attachment_by_tender_id_and_row_id as _download_buyer_attachment
)


class ReadBuyerAttachmentDocInput(BaseModel):
    """Input schema for the read_buyer_attachment_doc tool."""
    tender_id: str = Field(
        description="The tender ID (licitación ID) from Mercado Público"
    )
    row_id: int = Field(
        description="The row ID of the attachment to read (from the attachments table)"
    )
    start_page: Optional[int] = Field(
        default=None,
        description="Starting page number (1-indexed). If not specified, starts from page 1"
    )
    end_page: Optional[int] = Field(
        default=None,
        description="Ending page number (1-indexed, inclusive). If not specified, reads until last page"
    )


@tool(args_schema=ReadBuyerAttachmentDocInput)
def read_buyer_attachment_doc(
    tender_id: str,
    row_id: int,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None
) -> dict:
    """Read and extract text from a buyer attachment PDF document using Mistral OCR.

    This tool downloads a tender attachment and extracts text content using
    Mistral's OCR API. The OCR preserves document structure and returns markdown-formatted text.
    You can optionally specify a page range to read.

    Use this tool when you need to:
    - Extract text content from tender PDF documents (including scanned PDFs)
    - Analyze document content with preserved structure (tables, lists, headers)
    - Read technical specifications, budgets, certificates, and other tender documents
    - Read specific page ranges from large documents

    Args:
        tender_id: The tender ID (licitación ID) from Mercado Público
        row_id: The row ID of the attachment (use read_buyer_attachments_table to get this)
        start_page: Starting page number (1-indexed). Defaults to 1 if not specified
        end_page: Ending page number (1-indexed, inclusive). Defaults to last page if not specified

    Returns:
        dict: A dictionary containing:
            - text (str): Extracted text content in markdown format
            - total_pages (int): Total number of pages in the document
            - pages_read (list[int]): List of page numbers that were read (1-indexed)
            - file_size (int): Size of the file in bytes
            - success (bool): Whether the operation was successful
            - error (str, optional): Error message if operation failed
    """
    # Check for Mistral API key
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        return {
            "text": None,
            "total_pages": 0,
            "pages_read": [],
            "file_size": 0,
            "success": False,
            "error": "MISTRAL_API_KEY environment variable not set"
        }

    try:
        # Download the file content
        file_content = _download_buyer_attachment(tender_id, row_id)
        file_size = len(file_content)

        # Encode PDF to base64
        base64_pdf = base64.b64encode(file_content).decode('utf-8')

        # Initialize Mistral client
        client = Mistral(api_key=api_key)

        # Build pages array for Mistral API if start_page or end_page specified
        pages_to_process = None

        if start_page is not None or end_page is not None:
            # Convert from 1-indexed to 0-indexed
            start = (start_page - 1) if start_page else 0
            # End is inclusive in user input, but we need to handle it correctly for range
            # If end_page is None, we'll process all pages (handled by not setting pages param)
            if end_page is not None:
                # Build range list (Mistral expects array of page numbers, 0-indexed)
                pages_to_process = list(range(start, end_page))  # end_page is already inclusive in 1-indexed, so we use it directly

        # Prepare OCR request parameters
        ocr_params = {
            "model": "mistral-ocr-latest",
            "document": {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_pdf}"
            },
            "include_image_base64": False  # We only need text, not images
        }

        # Add pages parameter if specified
        if pages_to_process is not None:
            ocr_params["pages"] = pages_to_process

        # Call Mistral OCR API
        ocr_response = client.ocr.process(**ocr_params)

        # Extract text from response
        extracted_text = []
        pages_read = []

        for page in ocr_response.pages:
            page_num = page.index  # 0-indexed in response
            markdown_text = page.markdown

            if markdown_text:
                extracted_text.append(f"--- Page {page_num + 1} ---\n{markdown_text}")
                pages_read.append(page_num + 1)  # Convert to 1-indexed for return

        combined_text = "\n\n".join(extracted_text)

        # Get total pages from response
        # If we requested specific pages, the total_pages is from usage_info.num_pages
        # Otherwise, it's the length of pages returned
        if hasattr(ocr_response, 'usage_info') and hasattr(ocr_response.usage_info, 'num_pages'):
            total_pages = ocr_response.usage_info.num_pages
        else:
            total_pages = len(ocr_response.pages)

        return {
            "text": combined_text,
            "total_pages": total_pages,
            "pages_read": pages_read,
            "file_size": file_size,
            "success": True
        }

    except Exception as e:
        return {
            "text": None,
            "total_pages": 0,
            "pages_read": [],
            "file_size": 0,
            "success": False,
            "error": str(e)
        }

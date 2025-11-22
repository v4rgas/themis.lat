import tempfile
import os
from pathlib import Path
from pydantic import BaseModel, Field
from langchain.tools import tool

from app.tools.read_supplier_attachments import (
    download_buyer_attachment_by_tender_id_and_row_id as _download_buyer_attachment,
    read_buyer_attachments_table
)


class DownloadBuyerAttachmentInput(BaseModel):
    """Input schema for the download_buyer_attachment tool."""
    tender_id: str = Field(
        description="The tender ID (licitación ID) from Mercado Público"
    )
    row_id: int = Field(
        description="The row ID of the attachment to download (from the attachments table)"
    )


@tool(args_schema=DownloadBuyerAttachmentInput)
def download_buyer_attachment(tender_id: str, row_id: int) -> dict:
    """Download a buyer attachment from a specific tender to a temporary directory.

    This tool downloads a specific attachment file from a Mercado Público tender
    and saves it to a temporary directory. For PDF files, it also returns the total
    number of pages and instructions on how to read them.

    Use this tool when you need to:
    - Download a specific attachment file from a tender
    - Get metadata about PDF documents (page count)
    - Know how to read the document with read_buyer_attachment_doc tool

    Args:
        tender_id: The tender ID (licitación ID) from Mercado Público
        row_id: The row ID of the attachment (use read_buyer_attachments_table to get this)

    Returns:
        dict: A dictionary containing:
            - file_path (str): Full path to the downloaded file in temp directory
            - file_name (str): Original filename from the tender
            - total_pages (int, optional): Number of pages if PDF, None otherwise
            - read_instructions (str, optional): How to read this document with read_buyer_attachment_doc
            - success (bool): Whether the download was successful
            - error (str, optional): Error message if download failed
    """
    try:
        # Get attachment metadata to retrieve the filename
        attachments = read_buyer_attachments_table(tender_id)

        # Find the attachment with matching row_id
        file_name = None
        for attachment in attachments[1:]:  # Skip header row
            if attachment[0] == row_id:
                file_name = attachment[1]  # file_name is at index 1
                break

        if not file_name:
            return {
                "file_path": None,
                "file_name": None,
                "success": False,
                "error": f"Attachment with row_id {row_id} not found for tender {tender_id}"
            }

        # Download the file content
        file_content = _download_buyer_attachment(tender_id, row_id)

        # Create temp directory if it doesn't exist
        temp_dir = tempfile.gettempdir()
        temp_subdir = os.path.join(temp_dir, "mercado_publico_attachments")
        os.makedirs(temp_subdir, exist_ok=True)

        # Generate unique filename to avoid collisions
        safe_filename = f"{tender_id}_{row_id}_{file_name}"
        file_path = os.path.join(temp_subdir, safe_filename)

        # Save the file
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Try to get page count for PDFs
        total_pages = None
        read_instructions = None

        if file_name.lower().endswith('.pdf'):
            try:
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                total_pages = len(reader.pages)
                read_instructions = (
                    f"To read this PDF ({total_pages} pages), use read_buyer_attachment_doc with:\n"
                    f"- tender_id: '{tender_id}'\n"
                    f"- row_id: {row_id}\n"
                    f"- start_page: 1 (or your desired start page)\n"
                    f"- end_page: {total_pages} (or your desired end page)\n"
                    f"Example: To read first 3 pages, use start_page=1 and end_page=3"
                )
            except Exception:
                # If we can't read PDF, just skip page count
                read_instructions = (
                    f"To read this PDF, use read_buyer_attachment_doc with:\n"
                    f"- tender_id: '{tender_id}'\n"
                    f"- row_id: {row_id}\n"
                    f"- start_page and end_page (optional, defaults to all pages)"
                )

        return {
            "file_path": file_path,
            "file_name": file_name,
            "total_pages": total_pages,
            "read_instructions": read_instructions,
            "success": True
        }

    except Exception as e:
        return {
            "file_path": None,
            "file_name": None,
            "success": False,
            "error": str(e)
        }

import base64
import os
import tempfile
from pydantic import BaseModel, Field
from langchain.tools import tool
import requests
from bs4 import BeautifulSoup
from mistralai import Mistral
from app.tools.read_award_result import extract_qs_from_award_page, fetch_award_modal_html, download_award_attachment_by_row_id
from app.config import settings

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
    """Extract text from award result attachment PDF using OCR. ALWAYS preview (pages 1-2) before reading more.

    Args:
        id: Tender/acquisition ID from Mercado Público (e.g., "4074-24-LE19")
        row_id: Attachment ID from read_award_result attachments list (0-indexed)
        start_page: Start page (1-indexed, REQUIRED)
        end_page: End page (1-indexed inclusive, REQUIRED)

    Returns:
        dict: {text, total_pages, pages_read, file_size, success, error?}
    """
    api_key = settings.mistral_api_key
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
        temp_dir = tempfile.gettempdir()
        temp_subdir = os.path.join(temp_dir, "mercado_publico_award_attachments")
        os.makedirs(temp_subdir, exist_ok=True)
        
        cache_filename = f"{id}_{row_id}.pdf"
        cache_path = os.path.join(temp_subdir, cache_filename)
        
        if os.path.exists(cache_path):
            with open(cache_path, 'rb') as f:
                file_content = f.read()
            file_size = len(file_content)
        else:
            BASE_URL = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=<ID>"
            url = BASE_URL.replace("<ID>", id)
            
            response = requests.get(url, timeout=30.0)
            response.raise_for_status()
            main_html = response.text
            
            qs = extract_qs_from_award_page(main_html)
            modal_html = fetch_award_modal_html(qs)
            
            soup = BeautifulSoup(modal_html, 'html.parser')
            
            file_content = download_award_attachment_by_row_id(qs, soup, row_id)
            file_size = len(file_content)
            
            with open(cache_path, 'wb') as f:
                f.write(file_content)

        base64_pdf = base64.b64encode(file_content).decode('utf-8')

        client = Mistral(api_key=api_key)

        start = start_page - 1
        pages_to_process = list(range(start, end_page))

        ocr_params = {
            "model": "mistral-ocr-latest",
            "document": {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_pdf}"
            },
            "include_image_base64": False
        }

        ocr_params["pages"] = pages_to_process

        ocr_response = client.ocr.process(**ocr_params)

        extracted_text = []
        pages_read = []

        for page in ocr_response.pages:
            page_num = page.index
            markdown_text = page.markdown

            if markdown_text:
                extracted_text.append(f"--- Page {page_num + 1} ---\n{markdown_text}")
                pages_read.append(page_num + 1)

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
            "success": True
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

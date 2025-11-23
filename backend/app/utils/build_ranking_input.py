"""
Helper function to build RankingInput from TenderResponse and documents
"""
from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime
from app.utils.get_tender import TenderResponse
from app.schemas import RankingInput
from app.tools.read_supplier_attachments import read_buyer_attachments_table as _read_buyer_attachments_table
from app.utils.websocket_manager import manager
# Import underlying functions instead of LangChain tools
from app.tools.read_supplier_attachments import (
    download_buyer_attachment_by_tender_id_and_row_id
)
from mistralai import Mistral
from app.config import settings
import base64
from app.utils.document_reader import (
    detect_file_type,
    get_file_extension_from_mime,
    extract_text_locally
)
from app.utils.cache_manager import get_cache_manager


def build_ranking_input(
    tender_response: TenderResponse,
    tender_documents: List[Dict[str, Any]] = None
) -> RankingInput:
    """
    Build RankingInput from TenderResponse and optional document content.

    Args:
        tender_response: TenderResponse from get_tender()
        tender_documents: Optional list of documents with extracted content

    Returns:
        RankingInput ready for the ranking agent
    """
    # Extract basic information
    tender_id = tender_response.tenderId
    tender_name = tender_response.name
    tender_date = tender_response.TenderDate.publish.isoformat()

    # Build bases from description and evaluation criteria
    bases_parts = []

    # Add description
    if tender_response.description:
        bases_parts.append(f"Descripción:\n{tender_response.description}\n")

    # Add evaluation criteria
    if tender_response.TenderEvaluationCriteria:
        bases_parts.append("\nCriterios de Evaluación:")
        for criteria in tender_response.TenderEvaluationCriteria:
            bases_parts.append(
                f"- {criteria.item_name} (Ponderación: {criteria.ponderation}%)"
            )
            if criteria.observation:
                bases_parts.append(f"  Observación: {criteria.observation}")

    # Add guarantees
    if tender_response.TenderGuarantees:
        bases_parts.append("\nGarantías Requeridas:")
        for guarantee in tender_response.TenderGuarantees:
            bases_parts.append(
                f"- {guarantee.title}: {guarantee.description} "
                f"(Monto: {guarantee.amount} {guarantee.currency})"
            )

    bases = "\n".join(bases_parts) if bases_parts else "No hay bases disponibles"

    # Build bases_tecnicas from documents if available
    bases_tecnicas_parts = []

    if tender_documents:
        for doc in tender_documents:
            if doc.get("content"):
                doc_name = doc.get("name", "Documento")
                bases_tecnicas_parts.append(f"\n=== {doc_name} ===")
                bases_tecnicas_parts.append(doc["content"])

    if bases_tecnicas_parts:
        bases_tecnicas = "\n".join(bases_tecnicas_parts)
    else:
        # Provide helpful message when no documents are available
        bases_tecnicas = """
NOTA: No se pudieron obtener documentos técnicos para este tender.

Esto puede ocurrir por:
- El tender no tiene documentos adjuntos públicos
- Los documentos no están disponibles en Mercado Público
- Error al acceder a los documentos

El análisis se basará únicamente en la metadata disponible del tender
(descripción, criterios de evaluación, garantías, etc.).
"""

    # Build additional context
    additional_context = {
        "status": tender_response.status,
        "status_code": tender_response.statusCode,
        "publish_date": tender_response.TenderDate.publish.isoformat(),
        "close_date": tender_response.TenderDate.close.isoformat(),
        "organization": tender_response.tenderPurchaseData.organization.name,
        "organization_tax_number": tender_response.tenderPurchaseData.organization.tax_number,
        "unit": tender_response.tenderPurchaseData.orgUnit.name,
        "unit_address": tender_response.tenderPurchaseData.orgUnit.address,
        "unit_city": tender_response.tenderPurchaseData.orgUnit.city,
        "unit_region": tender_response.tenderPurchaseData.orgUnit.region,
        "institution": tender_response.tenderPurchaseData.organization.institution.name,
        "institution_category": tender_response.tenderPurchaseData.organization.institution.category,
        "evaluation_criteria_count": len(tender_response.TenderEvaluationCriteria),
        "guarantees_count": len(tender_response.TenderGuarantees),
    }

    return RankingInput(
        tender_id=tender_id,
        tender_name=tender_name,
        tender_date=tender_date,
        bases=bases,
        bases_tecnicas=bases_tecnicas,
        additional_context=additional_context
    )


def _send_log(session_id: Optional[str], message: str):
    """
    Helper to send WebSocket log messages.

    Args:
        session_id: Optional session ID for WebSocket streaming
        message: Log message to send
    """
    if session_id:
        try:
            asyncio.run(manager.send_observation(session_id, {
                "type": "log",
                "message": message,
                "timestamp": datetime.now().isoformat()
            }))
        except Exception as e:
            import traceback
            print(f"Failed to send log to WebSocket: {e}")
            traceback.print_exc()


def fetch_and_extract_documents(
    tender_id: str,
    max_docs: int = 3,
    session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch and extract content from tender documents.

    Args:
        tender_id: Tender ID
        max_docs: Maximum number of documents to fetch (default 3)
        session_id: Optional session ID for WebSocket streaming

    Returns:
        List of documents with extracted content (may be empty if no docs available)
    """
    documents = []

    # Get cache manager
    cache = get_cache_manager()

    try:
        # Get list of attachments
        attachments = _read_buyer_attachments_table(tender_id)

        # Handle case where attachments is None or not a list
        if not attachments:
            _send_log(session_id, "No attachments found for tender")
            print(f"No attachments found for tender {tender_id}")
            return documents

        if not isinstance(attachments, list):
            _send_log(session_id, f"Unexpected attachments format: {type(attachments)}")
            print(f"Unexpected attachments format for tender {tender_id}: {type(attachments)}")
            return documents

        _send_log(session_id, f"Found {len(attachments)} attachments available")
        print(f"Found {len(attachments)} attachments for tender {tender_id}")

        # Process up to max_docs documents
        docs_to_process = min(max_docs, len(attachments))
        for idx, attachment in enumerate(attachments[:max_docs]):
            try:
                # Get attachment name
                att_name = attachment.get("name", f"Document {idx + 1}") if isinstance(attachment, dict) else f"Document {idx + 1}"

                _send_log(session_id, f"Processing document {idx+1}/{docs_to_process}: {att_name}")
                print(f"  Attempting to read document {idx + 1}: {att_name}")

                # Download the file content
                file_content = download_buyer_attachment_by_tender_id_and_row_id(tender_id, idx)

                # Detect file type
                try:
                    mime_type = detect_file_type(file_content)
                except Exception as e:
                    print(f"  Warning: Could not detect file type, defaulting to PDF: {e}")
                    mime_type = "application/pdf"

                combined_text = ""

                # Try local extraction for DOCX files
                if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    local_result = extract_text_locally(file_content, mime_type)

                    if local_result["success"]:
                        text = local_result["text"]
                        if len(text) >= 100:
                            combined_text = text
                            print(f"  ✓ Successfully extracted text from DOCX (local)")

                            # Cache the extracted DOCX text (save as page 1)
                            cache.set_ocr_result(tender_id, idx, 1, text)
                        else:
                            print(f"  ✗ DOCX text too short ({len(text)} chars), skipping")
                            continue
                    else:
                        print(f"  ✗ Failed to extract text from DOCX: {local_result.get('error', 'Unknown error')}")
                        continue
                
                # For PDFs and images, use Mistral OCR
                else:
                    api_key = settings.mistral_api_key
                    if not api_key:
                        print(f"  ✗ MISTRAL_API_KEY not set, skipping document {idx + 1}")
                        continue

                    # Encode to base64
                    base64_file = base64.b64encode(file_content).decode('utf-8')

                    # Initialize Mistral client
                    client = Mistral(api_key=api_key)

                    # Read first 5 pages (0-indexed: 0-4)
                    start_page = 1
                    end_page = 5
                    pages_to_process = list(range(start_page - 1, end_page))

                    # Call Mistral OCR API
                    ocr_response = client.ocr.process(
                        model="mistral-ocr-latest",
                        document={
                            "type": "document_url",
                            "document_url": f"data:{mime_type};base64,{base64_file}"
                        },
                        pages=pages_to_process,
                        include_image_base64=False
                    )

                    # Extract text from response
                    extracted_text = []
                    pages_read = []

                    for page in ocr_response.pages:
                        page_num = page.index  # 0-indexed
                        markdown_text = page.markdown

                        if markdown_text:
                            extracted_text.append(f"--- Page {page_num + 1} ---\n{markdown_text}")
                            pages_read.append(page_num + 1)

                            # Cache this page's OCR result
                            cache.set_ocr_result(tender_id, idx, page_num + 1, markdown_text)

                    combined_text = "\n\n".join(extracted_text)

                if combined_text:
                    documents.append({
                        "row_id": idx + 1,
                        "name": att_name,
                        "content": combined_text,
                        "pages_read": "1-5"
                    })
                    print(f"  ✓ Successfully read document {idx + 1}")
                else:
                    print(f"  ✗ Document {idx + 1} has no content")

            except Exception as e:
                # Skip documents that fail to load
                import traceback
                error_msg = f"{type(e).__name__}: {str(e)}"
                _send_log(session_id, f"✗ Failed to extract document {idx + 1}: {error_msg}")
                print(f"  ✗ Could not load document {idx + 1}: {error_msg}")
                traceback.print_exc()
                continue

    except Exception as e:
        # Don't fail the entire workflow if documents can't be fetched
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        _send_log(session_id, f"Warning: Could not fetch attachments - {error_msg}")
        print(f"Warning: Could not fetch attachments for {tender_id}: {error_msg}")
        traceback.print_exc()
        print("Continuing without document content...")

    return documents
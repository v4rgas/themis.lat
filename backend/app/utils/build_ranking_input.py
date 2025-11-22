"""
Helper function to build RankingInput from TenderResponse and documents
"""
from typing import Dict, Any, List
from app.utils.get_tender import TenderResponse
from app.schemas import RankingInput
from app.tools.read_buyer_attachments_table import read_buyer_attachments_table
from app.tools.read_buyer_attachment_doc import read_buyer_attachment_doc


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


def fetch_and_extract_documents(tender_id: str, max_docs: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch and extract content from tender documents.

    Args:
        tender_id: Tender ID
        max_docs: Maximum number of documents to fetch (default 3)

    Returns:
        List of documents with extracted content (may be empty if no docs available)
    """
    documents = []

    try:
        # Get list of attachments
        attachments = read_buyer_attachments_table(tender_id)

        # Handle case where attachments is None or not a list
        if not attachments:
            print(f"No attachments found for tender {tender_id}")
            return documents

        if not isinstance(attachments, list):
            print(f"Unexpected attachments format for tender {tender_id}: {type(attachments)}")
            return documents

        print(f"Found {len(attachments)} attachments for tender {tender_id}")

        # Process up to max_docs documents
        for idx, attachment in enumerate(attachments[:max_docs]):
            try:
                # Get attachment name
                att_name = attachment.get("name", f"Document {idx + 1}") if isinstance(attachment, dict) else f"Document {idx + 1}"

                print(f"  Attempting to read document {idx + 1}: {att_name}")

                # Extract first few pages to get overview
                doc_content = read_buyer_attachment_doc(
                    tender_id=tender_id,
                    row_id=idx + 1,  # Usually 1-indexed
                    start_page=1,
                    end_page=5  # Read first 5 pages
                )

                if doc_content and isinstance(doc_content, dict):
                    content = doc_content.get("content", "")
                    if content:
                        documents.append({
                            "row_id": idx + 1,
                            "name": att_name,
                            "content": content,
                            "pages_read": "1-5"
                        })
                        print(f"  ✓ Successfully read document {idx + 1}")
                    else:
                        print(f"  ✗ Document {idx + 1} has no content")
                else:
                    print(f"  ✗ Document {idx + 1} returned invalid format")

            except Exception as e:
                # Skip documents that fail to load
                print(f"  ✗ Could not load document {idx + 1}: {type(e).__name__}: {str(e)}")
                continue

    except Exception as e:
        # Don't fail the entire workflow if documents can't be fetched
        print(f"Warning: Could not fetch attachments for {tender_id}: {type(e).__name__}: {str(e)}")
        print("Continuing without document content...")

    return documents
from pydantic import BaseModel, Field
from langchain.tools import tool

from app.tools.read_supplier_attachments import read_buyer_attachments_table as _read_buyer_attachments_table


class ReadBuyerAttachmentsTableInput(BaseModel):
    """Input schema for the read_buyer_attachments_table tool."""
    tender_id: str = Field(
        description="The tender ID (licitación ID) from Mercado Público to retrieve attachments for"
    )


@tool(args_schema=ReadBuyerAttachmentsTableInput)
def read_buyer_attachments_table(tender_id: str) -> list:
    """Read the list of buyer attachments for a specific tender.

    This tool retrieves metadata about all attachments uploaded by the buyer
    for a given tender from Mercado Público (Chilean public procurement platform).

    Use this tool when you need to:
    - List all available attachments for a tender
    - Get metadata about tender documents (file names, types, sizes, descriptions)
    - Find the row_id needed to download a specific attachment

    Args:
        tender_id: The tender ID (licitación ID) from Mercado Público

    Returns:
        list: A list of attachments where the first element is the header
              ["id", "file_name", "type", "description", "file_size", "uploaded_at"]
              and subsequent elements are attachment data rows
    """
    return _read_buyer_attachments_table(tender_id)

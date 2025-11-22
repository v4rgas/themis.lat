from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.tools.read_supplier_attachments import (
    download_buyer_attachment_by_tender_id_and_row_id,
    read_buyer_attachments_table,
)

app = FastAPI(title="API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321", "http://frontend:4321"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/tender/{tender_id}/buyer-attachments-table")
def get_buyer_attachments_table(tender_id: str):
    return read_buyer_attachments_table(tender_id)


@app.get("/api/tender/{tender_id}/download-attachment/{row_id}")
def download_attachment(tender_id: str, row_id: int):
    content = download_buyer_attachment_by_tender_id_and_row_id(tender_id, row_id)
    return Response(content=content, media_type="application/octet-stream")

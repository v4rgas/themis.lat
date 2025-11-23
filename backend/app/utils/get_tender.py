import httpx
import asyncio
from pydantic import BaseModel
from datetime import datetime
from bs4 import BeautifulSoup
import re
from typing import Optional
from app.utils.cache_manager import get_cache_manager

class TenderDate(BaseModel):
    publish: datetime
    close: datetime


class TenderEvaluationCriteria(BaseModel):
    item_name: str
    observation: str
    ponderation: int
    row_index: int
    createdAt: datetime
    updatedAt: datetime


class TenderGuarantee(BaseModel):
    title: str
    description: str
    beneficiary: str
    due_date: datetime
    amount: float
    currency: str
    restitution_way: str
    gloss: str
    createdAt: datetime
    updatedAt: datetime


class Institution(BaseModel):
    code: str
    name: str
    category: str
    createdAt: datetime
    updatedAt: datetime


class Organization(BaseModel):
    tax_number: str
    name: str
    createdAt: datetime
    updatedAt: datetime
    institution_code: str
    institution: Institution


class OrgUnit(BaseModel):
    code: str
    name: str
    address: str
    city: str
    region: str
    createdAt: datetime
    updatedAt: datetime
    organization_tax_number: str


class TenderPurchaseData(BaseModel):
    id: int
    createdAt: datetime
    updatedAt: datetime
    organization_tax_number: str
    unit_code: str
    tender_id: str
    buying_user_id: str
    organization: Organization
    orgUnit: OrgUnit


class TenderType(BaseModel):
    description: str
    currency: str


class TenderResponse(BaseModel):
    tenderId: str
    name: str
    description: str
    status: str
    statusCode: int
    TenderDate: TenderDate
    TenderEvaluationCriteria: list[TenderEvaluationCriteria]
    TenderGuarantees: list[TenderGuarantee]
    tenderPurchaseData: TenderPurchaseData
    type: Optional[TenderType] = None


async def extract_qs_from_tender_page(tender_id: str, client: httpx.AsyncClient) -> Optional[str]:
    url = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={tender_id}"

    # Check cache first
    cache = get_cache_manager()
    cached_html = cache.get_html(url, max_age_seconds=3600)  # 1 hour TTL

    try:
        if cached_html:
            html = cached_html
            print(f"[CACHE HIT] HTML: tender page {tender_id} (extract QS)")
        else:
            response = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            html = response.text
            # Cache the response
            cache.set_html(url, html)
            print(f"[CACHE MISS] HTML: tender page {tender_id} (cached)")

        soup = BeautifulSoup(html, 'html.parser')
        
        img_element = soup.find('input', {'id': 'imgAdjudicacion'})
        if not img_element:
            img_element = soup.find('a', {'id': 'imgAdjudicacion'})
        if not img_element:
            img_element = soup.find(id='imgAdjudicacion')
        
        if not img_element:
            return None
        
        href = img_element.get('href', '')
        match = re.search(r'qs=([^&"]+)', href)
        if not match:
            return None

        return match.group(1)
    except Exception as e:
        import traceback
        print(f"Error extracting qs from tender page: {e}")
        traceback.print_exc()
        return None


async def fetch_tender_type(qs: str, client: httpx.AsyncClient) -> Optional[TenderType]:
    url = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?qs={qs}"

    # Check cache first
    cache = get_cache_manager()
    cached_html = cache.get_html(url, max_age_seconds=3600)  # 1 hour TTL

    try:
        if cached_html:
            html = cached_html
            print(f"[CACHE HIT] HTML: tender type qs={qs[:20]}...")
        else:
            response = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            html = response.text
            # Cache the response
            cache.set_html(url, html)
            print(f"[CACHE MISS] HTML: tender type qs={qs[:20]}... (cached)")

        soup = BeautifulSoup(html, 'html.parser')
        
        type_span = soup.find('span', id='lblFicha1Tipo')
        currency_span = soup.find('span', id='lblFicha1Moneda')
        
        if not type_span or not currency_span:
            return None
        
        description = type_span.get_text(strip=True)
        currency = currency_span.get_text(strip=True)
        
        if not description or not currency:
            return None
        
        return TenderType(description=description, currency=currency)
    except Exception as e:
        import traceback
        print(f"Error fetching tender type: {e}")
        traceback.print_exc()
        return None


async def get_tender(tender_id: str) -> TenderResponse:
    url = f"https://api.licitalab.cl/free/tender/{tender_id}"
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        api_response, qs = await asyncio.gather(
            client.get(url),
            extract_qs_from_tender_page(tender_id, client)
        )
        
        api_response.raise_for_status()
        tender_data = TenderResponse.model_validate(api_response.json())
    
    if qs:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            tender_type = await fetch_tender_type(qs, client)
            if tender_type:
                tender_data.type = tender_type
    
    return tender_data


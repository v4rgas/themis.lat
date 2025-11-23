import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
import re
import logging
from pydantic import BaseModel, Field
from langchain.tools import tool
from app.utils.cache_manager import get_cache_manager

logger = logging.getLogger(__name__)


def normalize_value(value: str) -> Optional[str]:
    return None if value == "--" else value


def extract_qs_from_award_page(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    
    img_element = soup.find('input', {'id': 'imgAdjudicacion'})
    if not img_element:
        img_element = soup.find('a', {'id': 'imgAdjudicacion'})
    if not img_element:
        img_element = soup.find(id='imgAdjudicacion')
    
    if not img_element:
        with open('debug_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
        raise Exception("Could not find imgAdjudicacion element. Saved HTML to debug_page.html")
    
    href = img_element.get('href', '')
    
    match = re.search(r'qs=([^&"]+)', href)
    if not match:
        raise Exception("Could not extract qs parameter from href")
    
    return match.group(1)


def fetch_award_modal_html(qs: str) -> str:
    url = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/StepsProcessAward/PreviewAwardAct.aspx?qs={qs}"

    # Check cache first
    cache = get_cache_manager()
    cached_html = cache.get_html(url, max_age_seconds=3600)  # 1 hour TTL

    if cached_html:
        print(f"[CACHE HIT] HTML: award modal qs={qs[:20]}...")
        logger.info(f"Using cached award modal HTML for qs={qs} (length={len(cached_html)})")
        return cached_html

    logger.info(f"Fetching award modal HTML with qs={qs}")
    try:
        response = requests.get(url, timeout=30.0)
        response.raise_for_status()
        html = response.text

        # Cache the response
        cache.set_html(url, html)

        print(f"[CACHE MISS] HTML: award modal qs={qs[:20]}... (cached for future use)")
        logger.info(f"Successfully fetched and cached award modal HTML (status={response.status_code}, length={len(html)})")
        return html
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch award modal HTML: {type(e).__name__}: {str(e)}")
        raise


def parse_attachments(soup: BeautifulSoup) -> List[Dict[str, str]]:
    attachments = []
    attachments_section = soup.find('span', string=lambda text: text and 'Anexos a la Adjudicación' in text)
    
    if attachments_section:
        table = soup.find('table', id='DWNL_grdId')
        if table:
            rows = table.find_all('tr')[1:]
            for row_id, row in enumerate(rows):
                cells = row.find_all('td')
                if len(cells) >= 6:
                    file_span = cells[1].find('span')
                    type_span = cells[2].find('span')
                    desc_span = cells[3].find('span')
                    size_span = cells[4].find('span')
                    date_span = cells[5].find('span')
                    
                    attachment = {
                        'row_id': row_id,
                        'file': file_span.get_text(strip=True) if file_span else '',
                        'type': type_span.get_text(strip=True) if type_span else '',
                        'description': desc_span.get_text(strip=True) if desc_span else '',
                        'size': size_span.get_text(strip=True) if size_span else '',
                        'date': date_span.get_text(strip=True) if date_span else ''
                    }
                    attachments.append(attachment)
            
            parent_div = attachments_section.find_parent('div', style=lambda x: x and 'Width:100%' in x)
            if parent_div:
                parent_div.decompose()
            else:
                parent_div = attachments_section.find_parent('div')
                if parent_div:
                    parent_div.decompose()
    
    return attachments


def parse_overview(soup: BeautifulSoup) -> Dict[str, Any]:
    overview = {}
    
    award_act_marker = soup.find('span', id='lblAwardAct')
    if not award_act_marker:
        award_act_marker = soup.find('span', class_='cssLabelsData', string=lambda text: text and 'Acta Adjudicación' in text)
    
    if award_act_marker:
        labels_data = award_act_marker.find_all_previous('span', class_='cssLabelsData')
        labels_data.reverse()
    else:
        labels_data = soup.find_all('span', class_='cssLabelsData')
    
    for label_span in labels_data:
        if label_span.get('id') == 'lblAwardAct':
            break
        key = label_span.get_text(strip=True)
        if key == 'Acta Adjudicación':
            break
        parent_tr = label_span.find_parent('tr')
        if parent_tr:
            next_tr = parent_tr.find_next_sibling('tr')
            if next_tr:
                value_span = next_tr.find('span', class_='cssLabelsItemData')
                if value_span:
                    value = value_span.get_text(strip=True)
                    overview[key] = normalize_value(value)
    
    return overview


def parse_award_act(soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
    award_act = {}
    
    subtitle_tds = soup.find_all('td', class_='cssFwkLabelSubTitle')
    for td in subtitle_tds:
        subtitle_text = td.get_text(strip=True)
        if subtitle_text and subtitle_text != 'Acta Adjudicación':
            edit_table = td.find_next('table', class_='cssEditTable')
            if edit_table:
                subsection = {}
                rows = edit_table.find_all('tr')
                for row in rows:
                    title_td = row.find('td', class_='cssDataTitle')
                    if title_td:
                        key_span = title_td.find('span', class_='cssLabelsData')
                        if key_span:
                            subkey = key_span.get_text(strip=True)
                            value_td = row.find('td', class_='cssDataItem')
                            if value_td:
                                value_elem = value_td.find(class_='cssLabelsItemData')
                                if value_elem:
                                    value = value_elem.get_text(strip=True)
                                    subsection[subkey] = normalize_value(value)
                if subsection:
                    award_act[subtitle_text] = subsection
    
    return award_act


def extract_provider_url_from_onclick(onclick_attr: str) -> Optional[str]:
    if not onclick_attr:
        return None
    match = re.search(r"openPopUpTitle\('([^']+)'", onclick_attr)
    if match:
        return match.group(1)
    return None


def fetch_provider_details(enc_param: str) -> Dict[str, Optional[str]]:
    url = f"https://www.mercadopublico.cl/BID/Modules/PopUps/InformationProvider.aspx?enc={enc_param}"

    # Check cache first
    cache = get_cache_manager()
    cached_html = cache.get_html(url, max_age_seconds=3600)  # 1 hour TTL

    try:
        if cached_html:
            html = cached_html
            print(f"[CACHE HIT] HTML: provider details enc={enc_param[:20]}...")
            logger.info(f"Using cached provider details for enc={enc_param[:20]}...")
        else:
            response = requests.get(url, timeout=30.0)
            response.raise_for_status()
            html = response.text
            # Cache the response
            cache.set_html(url, html)
            print(f"[CACHE MISS] HTML: provider details enc={enc_param[:20]}... (cached)")
            logger.info(f"Fetched and cached provider details for enc={enc_param[:20]}...")

        soup = BeautifulSoup(html, 'html.parser')
        
        razon_social = None
        rut = None
        sucursal = None
        
        razon_social_span = soup.find('span', id='lblSocialReasonDesc')
        if razon_social_span:
            razon_social = razon_social_span.get_text(strip=True)
        
        rut_span = soup.find('span', id='lblRutDesc')
        if rut_span:
            rut = rut_span.get_text(strip=True)
        
        sucursal_span = soup.find('span', id='lblBranchDesc')
        if sucursal_span:
            sucursal = sucursal_span.get_text(strip=True)
        
        return {
            'razon_social': razon_social,
            'rut': rut,
            'sucursal': sucursal
        }
    except Exception as e:
        import traceback
        print(f"Error fetching provider details: {e}")
        traceback.print_exc()
        return {
            'razon_social': None,
            'rut': None,
            'sucursal': None
        }


def parse_award_result(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    award_results = []
    
    main_table = soup.find('table', id='grdItemOC')
    if not main_table:
        return award_results
    
    item_tables = main_table.find_all('table', id=lambda x: x and 'rptBids_' in x)
    
    for item_table in item_tables:
        item = {}
        
        parent_container = item_table.find_parent('td')
        if not parent_container:
            parent_container = item_table.find_parent('tr')
        
        number_span = item_table.find('span', id=lambda x: x and 'lblNumber' in x)
        if number_span:
            item['item_number'] = number_span.get_text(strip=True)
        
        onu_code_span = item_table.find('span', id=lambda x: x and 'lblCodeonu' in x)
        if onu_code_span:
            item['onu_code'] = onu_code_span.get_text(strip=True)
        
        schema_title_span = item_table.find('span', id=lambda x: x and 'LblSchemaTittle' in x)
        if schema_title_span:
            item['schema_title'] = schema_title_span.get_text(strip=True)
        
        description_span = item_table.find('span', id=lambda x: x and 'lblDescription' in x)
        if description_span:
            item['buyer_specifications'] = description_span.get_text(strip=True)
        
        quantity_span = item_table.find('span', id=lambda x: x and 'LblRBICuantityNumber' in x)
        if quantity_span:
            item['quantity'] = quantity_span.get_text(strip=True)
        
        bids_table = None
        if parent_container:
            bids_table = parent_container.find('table', id=lambda x: x and 'gvLines' in x)
        
        if not bids_table:
            bids_table = item_table.find_next('table', id=lambda x: x and 'gvLines' in x)
        
        if bids_table:
            bids = []
            rows = bids_table.find_all('tr')
            for row in rows:
                if 'cssPRCGridViewRow' in row.get('class', []) or 'cssPRCGridViewAltRow' in row.get('class', []):
                    cells = row.find_all('td')
                    if len(cells) >= 6:
                        provider_link = cells[0].find('a')
                        provider_span = provider_link.find('span') if provider_link else None
                        provider = provider_span.get_text(strip=True) if provider_span else ''
                        
                        supplier_comment_span = cells[1].find('span', id=lambda x: x and 'lblSupplierComment' in x)
                        supplier_comment = supplier_comment_span.get_text(strip=True) if supplier_comment_span else ''
                        
                        symbol_span = cells[2].find('span', id=lambda x: x and 'lblSymbol' in x)
                        price_span = cells[2].find('span', id=lambda x: x and 'lblTotalNetPrice' in x)
                        unit_price = ''
                        if symbol_span and price_span:
                            unit_price = f"{symbol_span.get_text(strip=True)} {price_span.get_text(strip=True)}"
                        
                        quantity_awarded_span = cells[3].find('span', id=lambda x: x and 'txtAwardedQuantity' in x)
                        quantity_awarded = quantity_awarded_span.get_text(strip=True) if quantity_awarded_span else ''
                        
                        total_awarded_span = cells[4].find('span', id=lambda x: x and 'lblTotalNetAward' in x)
                        total_awarded = total_awarded_span.get_text(strip=True) if total_awarded_span else ''
                        
                        status_span = cells[5].find('span', id=lambda x: x and 'lblIsSelected' in x)
                        status = status_span.get_text(strip=True) if status_span else ''
                        
                        bid = {
                            'provider': provider,
                            'supplier_specifications': supplier_comment,
                            'unit_offer_amount': unit_price,
                            'awarded_quantity': quantity_awarded,
                            'total_net_awarded': total_awarded,
                            'status': status
                        }
                        
                        if status == 'Adjudicada' and provider_link:
                            onclick_attr = provider_link.get('onclick', '')
                            provider_url = extract_provider_url_from_onclick(onclick_attr)
                            if provider_url:
                                match = re.search(r'enc=([^&\'"]+)', provider_url)
                                if match:
                                    enc_param = match.group(1)
                                    provider_details = fetch_provider_details(enc_param)
                                    bid['provider_details'] = provider_details
                        
                        bids.append(bid)
            
            item['bids'] = bids
        
        total_line_span = None
        if parent_container:
            total_line_span = parent_container.find('span', id=lambda x: x and 'lblTotalLine' in x)
        
        if not total_line_span:
            total_line_span = item_table.find_next('span', id=lambda x: x and 'lblTotalLine' in x)
        
        if total_line_span:
            item['total_line_amount'] = total_line_span.get_text(strip=True)
        
        if item:
            award_results.append(item)
    
    return award_results


def parse_details(soup: BeautifulSoup) -> Dict[str, Any]:
    details = {}
    
    acquisition_number_span = soup.find('span', id='lblTitlePorcNumberDesc')
    if acquisition_number_span:
        details['acquisition_number'] = acquisition_number_span.get_text(strip=True)
    
    award_date_span = soup.find('span', id='lblTitlePorcDateDesc')
    if award_date_span:
        details['award_informed_date'] = award_date_span.get_text(strip=True)
    
    return details


def extract_viewstate_params(soup: BeautifulSoup) -> Dict[str, str]:
    params = {}
    viewstate = soup.find("input", {"id": "__VIEWSTATE"})
    if viewstate:
        params["__VIEWSTATE"] = str(viewstate.get("value", ""))
    viewstategenerator = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})
    if viewstategenerator:
        params["__VIEWSTATEGENERATOR"] = str(viewstategenerator.get("value", ""))
    return params


def download_award_attachment_by_row_id(qs: str, soup: BeautifulSoup, row_id: int) -> bytes:
    html_id = str(row_id + 2).zfill(2)
    params = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        **extract_viewstate_params(soup),
        f"DWNL$grdId$ctl{html_id}$search.x": "30",
        f"DWNL$grdId$ctl{html_id}$search.y": "35",
        "DWNL$ctl10": "",
    }
    url = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/StepsProcessAward/PreviewAwardAct.aspx?qs={qs}"
    response = requests.post(url, data=params, timeout=30.0)
    response.raise_for_status()
    return response.content


class ReadAwardInput(BaseModel):
    id: str = Field(
        description="The tender/acquisition ID from Mercado Público to retrieve award information for"
    )


@tool(args_schema=ReadAwardInput)
def read_award_result(id: str) -> Dict[str, Any]:
    """Retrieve complete award information for a tender from Mercado Público.

    This tool fetches and parses detailed award data including attachments, overview, 
    award act details, bid results with provider details, and acquisition metadata from 
    the Chilean public procurement platform.

    Use this tool when you need to:
    - Get comprehensive award details for a specific tender
    - Analyze winning bids and awarded quantities
    - Extract awarded provider details (razón social, rut, sucursal)
    - Review award attachments and documentation
    - Extract procurement act details and resolutions

    Args:
        id: The tender/acquisition ID from Mercado Público (e.g., "4074-24-LE19")

    Returns:
        dict: A dictionary containing:
            - ok: Boolean indicating if award information is available
            - attachments: List of attached documents with metadata (row_id, file, type, description, size, date).
              Use row_id with read_award_result_attachment tool to download the actual file bytes
            - overview: Award act overview (vistos, considerando, resuelvo)
            - award_act: Structured award act details (buyer, contact, acquisition data)
            - award_result: Detailed bid information per item with all bids. For awarded bids 
              (status='Adjudicada'), includes provider_details with razón social, rut, and sucursal
            - details: Acquisition number and award informed date
    """
    BASE_URL = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=<ID>"
    url = BASE_URL.replace("<ID>", id)

    # Check cache first
    cache = get_cache_manager()
    main_html = cache.get_html(url, max_age_seconds=3600)  # 1 hour TTL

    if not main_html:
        response = requests.get(url, timeout=30.0)
        response.raise_for_status()
        main_html = response.text

        # Cache the response
        cache.set_html(url, main_html)
        print(f"[CACHE MISS] HTML: main acquisition page {id} (cached)")
        logger.info(f"Fetched and cached main acquisition page for {id}")
    else:
        print(f"[CACHE HIT] HTML: main acquisition page {id}")
        logger.info(f"Using cached main acquisition page for {id}")
    
    soup = BeautifulSoup(main_html, 'html.parser')
    img_element = soup.find('input', {'id': 'imgAdjudicacion'})
    if not img_element:
        img_element = soup.find('a', {'id': 'imgAdjudicacion'})
    if not img_element:
        img_element = soup.find(id='imgAdjudicacion')
    
    if not img_element:
        return {'ok': False}
    
    if img_element.get('disabled') == 'disabled':
        logger.warning(f"Award button is disabled for tender {id}")
        return {'ok': False}
    
    try:
        qs = extract_qs_from_award_page(main_html)
        logger.info(f"Extracted qs parameter: {qs}")
    except Exception as e:
        logger.error(f"Failed to extract qs parameter: {type(e).__name__}: {str(e)}")
        raise
    
    try:
        modal_html = fetch_award_modal_html(qs)
        logger.info(f"Modal HTML fetched successfully (length={len(modal_html)})")
    except Exception as e:
        logger.error(f"Failed to fetch modal HTML: {type(e).__name__}: {str(e)}")
        raise
    
    soup = BeautifulSoup(modal_html, 'html.parser')
    div_content = soup.find('div', id='divContent')
    
    if not div_content:
        logger.error(f"Could not find divContent in modal HTML for tender {id}")
        raise Exception("Could not find divContent in modal HTML")
    
    logger.info(f"Found divContent in modal HTML")
    
    content_soup = BeautifulSoup(str(div_content), 'html.parser')
    
    attachments = parse_attachments(content_soup)
    overview = parse_overview(content_soup)
    award_act = parse_award_act(content_soup)
    award_result = parse_award_result(content_soup)
    details = parse_details(content_soup)
    
    return {
        'ok': True,
        'attachments': attachments,
        'overview': overview,
        'award_act': award_act,
        'award_result': award_result,
        'details': details
    }

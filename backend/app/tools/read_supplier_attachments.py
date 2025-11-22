import requests
from bs4 import BeautifulSoup
import warnings

warnings.filterwarnings("ignore")

s = requests.Session()
# s.verify = False

headers = {
    "Host": "www.mercadopublico.cl",
    "Sec-Ch-Ua": '"Chromium";v="141", "Not?A_Brand";v="8"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Accept-Language": "es-ES,es;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    # 'Accept-Encoding': 'gzip, deflate, br',
    "Priority": "u=0, i",
    "Connection": "keep-alive",
}


def extract_viewstate_params(soup: BeautifulSoup) -> dict[str, str]:
    """Extract __VIEWSTATE and __VIEWSTATEGENERATOR from a BeautifulSoup object."""
    params = {}
    viewstate = soup.find("input", {"id": "__VIEWSTATE"})
    if viewstate:
        params["__VIEWSTATE"] = str(getattr(viewstate, "attrs").get("value"))
    viewstategenerator = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})
    if viewstategenerator:
        params["__VIEWSTATEGENERATOR"] = str(
            getattr(viewstategenerator, "attrs").get("value")
        )
    return params


def get_tender_data_by_id(tender_id: str) -> BeautifulSoup:
    """
    Returns a BeautifulSoup object containing the tender's data from the given tender ID.
    """
    url = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={tender_id}"
    response = s.get(url, headers=headers)
    return BeautifulSoup(response.text, "lxml")


def get_url_for_popup_with_html_id(soup: BeautifulSoup, html_id: str) -> str | None:
    """
    Returns the URL of the provided popup, identified by the html_id,
    from the given tender data BeautifulSoup object.
    """
    inputs = soup.find_all("input", {"id": html_id})
    href_or_onclick = None
    for input_ in inputs:
        if hasattr(input_, "attrs"):
            attrs = getattr(input_, "attrs")
            href = attrs.get("href")
            onclick = attrs.get("onclick")
            if href:
                href = str(href)
                break
            elif onclick:
                href_or_onclick = str(onclick)
                if href_or_onclick.startswith("open('"):
                    href_or_onclick = href_or_onclick.split("'")[1]
                    break
    return href_or_onclick


def get_anexos_comprador_page(href: str | None) -> BeautifulSoup | None:
    """
    Returns a BeautifulSoup object containing the tender's buyer's attachments page from the given URL.
    """
    if not href:
        return None
    response = s.get(
        "https://www.mercadopublico.cl/Procurement/Modules/RFB/" + href, headers=headers
    )
    return BeautifulSoup(response.text, "lxml")


def extract_anexos_comprador_from_soup(soup: BeautifulSoup) -> BeautifulSoup | None:
    """
    Extracts the tender's buyer's attachments page from the given BeautifulSoup object.
    """
    table = soup.find("table", {"id": "DWNL_grdId"})
    if table:
        # find tr with class cssFwkItemStyle or cssFwkAlternatingItemStyle
        trs = table.find_all(
            "tr", class_=["cssFwkItemStyle", "cssFwkAlternatingItemStyle"]
        )
        td_texts = [
            ["id", "file_name", "type", "description", "file_size", "uploaded_at"]
        ]
        for row_id, tr in enumerate(trs):
            row_texts = []
            for td in tr.find_all("td")[1:-1]:
                row_texts.append(td.text.strip())
            td_texts.append([row_id, *row_texts])
        return td_texts


def download_anexo_comprador_by_row_id(
    href: str, soup: BeautifulSoup, row_id: int
) -> BeautifulSoup | None:
    """
    Downloads the tender's buyer's attachment by the given row ID, soup and href.
    """
    html_id = str(row_id + 2).zfill(2)
    params = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        **extract_viewstate_params(soup),
        f"DWNL$grdId$ctl{html_id}$search.x": "30",
        f"DWNL$grdId$ctl{html_id}$search.y": "35",
        "DWNL$ctl10": "",
    }
    response = s.post(
        "https://www.mercadopublico.cl/Procurement/Modules/RFB/" + href,
        data=params,
        headers=headers,
    )
    return response.content


def read_buyer_attachments_table(tender_id: str) -> list[str]:
    """
    Reads the supplier's attachments for the given tender ID.
    """
    soup = get_tender_data_by_id(tender_id)
    href = get_url_for_popup_with_html_id(soup, "imgAdjuntos")
    soup = get_anexos_comprador_page(href)
    td_texts = extract_anexos_comprador_from_soup(soup)
    return td_texts


def download_buyer_attachment_by_tender_id_and_row_id(
    tender_id: str, row_id: int
) -> bytes:
    """
    Downloads the tender's buyer's attachment by the given tender ID and row ID.
    """
    soup = get_tender_data_by_id(tender_id)
    href = get_url_for_popup_with_html_id(soup, "imgAdjuntos")
    soup = get_anexos_comprador_page(href)
    return download_anexo_comprador_by_row_id(href, soup, row_id)

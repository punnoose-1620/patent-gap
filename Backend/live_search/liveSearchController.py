import time
import json
import sys
import threading
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
from datetime import datetime
from file_controller import readFromXmlUrl, readFromPdfUrl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from llm_brain.gemini import Gemini
import models.infringements as infringement_model
import models.cases as case_model
from infringement_score_filters import (
    filter_infringement_entry,
    filter_similar_claims,
    score_meets_threshold,
)
from models.live_search_results import ProductTargetSources
from live_search.googleSearch import is_google_custom_search_configured, productGoogleSearch
from live_search.searchUrlBuilder import SearchUrlBuilderByKeywords
from live_search.caseDataUrlFromSearchResults import CaseDataUrlFromSearchResults

from web_scraper.free_patents_online import FreePatentsOnline
from web_scraper.google_patents import GooglePatents
from web_search import check_html_for_runtime_errors

TITLE_SIMILARITY_THRESHOLD = 0.85
DEFAULT_LLM_DELAY = 3       # Delay between processing 2 consecutive LLM calls (in seconds)
SEARCH_TIMEOUT = 10
DEFAULT_PRODUCT_SEARCH_MAX_RESULTS = 30
MAX_PRODUCT_SEARCH_MAX_RESULTS = 100
SESSION_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1'
}

def _tqdm(iterable, **kwargs):
    """Avoid tqdm OSError [Errno 22] in Flask background threads on Windows."""
    disable = kwargs.pop('disable', None)
    if disable is None:
        disable = not sys.stdout.isatty() or threading.current_thread() is not threading.main_thread()
    return tqdm(iterable, disable=disable, **kwargs)

SOURCES = [
    {
        'title': 'Free Patents Online',
        'search_url': 'https://www.freepatentsonline.com/result.html',
        'url_builder_selector': 'free-patents-online',
        'parameters': ['keywords'],
        'scope': ['United States'],
        'search_tags': {
            'case_data': 'a',
            'match_score': 'td-3',
            'patent_id': 'td-1',
            'title': 'td-2'
        },
        'search_ids' : {},
        'search_classes_to_drop': [],
        'details_tag': {},
        'details_ids': {},
        'details_class_to_isolate': ['fixed-width document-details-wrapper'],
        'details_id_to_isolate': [],
        'use_gemini_for_details': True
    },
    {
        'title': 'Google Patents',
        'search_url': 'https://patents.google.com',
        'url_builder_selector': 'google-patents',
        'parameters': ['keywords'],
        'scope': ['United States', 'Europe'],
        'search_tags' : {},
        'search_ids' : {
            'case_data': 'link'
        },
        'search_classes_to_drop': ['header', 'pageFooter'],
        'details_tag': {},
        'details_ids': {
            'claims': 'text'
        },
        'details_class_to_isolate': [],
        'details_id_to_isolate': ['wrapper'],
        'use_gemini_for_details': True
    }
]

def calculate_cosine_similarity(text1: str, text2: str) -> float:
    """Calculate cosine similarity between two text strings."""
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform([text1, text2])
    return cosine_similarity(vectors[0], vectors[1])[0][0]

def checkSimilarTitleExists(title1:str, references: list[str]):
    for reference in references:
        similarity = calculate_cosine_similarity(title1, reference)
        if similarity > TITLE_SIMILARITY_THRESHOLD:
            return True
    return False

def _live_result_to_dict(obj, case_id: str = ''):
    """Convert LiveSearchResults (or similar) to a JSON-serializable dict for API and alreadyExists()."""
    if obj is None:
        return None
    if hasattr(obj, 'model_dump'):
        d = obj.model_dump()
    elif hasattr(obj, 'dict'):
        d = obj.dict()
    else:
        d = dict(obj) if isinstance(obj, dict) else obj
    if not isinstance(d, dict):
        return d
    if isinstance(d.get('claims'), dict) and 'claims' in d['claims']:
        d['claims'] = d['claims']['claims']
    # Pydantic v2 omits leading-underscore fields from model_dump; use patent id from URL.
    patent_id = case_id or d.get('case_id') or d.get('_id') or ''
    if patent_id:
        d['case_id'] = patent_id
        d['_id'] = patent_id
    return d

def claims_to_strings(claims) -> list[str]:
    """Normalize case claims (list[str] or dict of SingleClaim) to plain strings for Gemini."""
    if not claims:
        return []
    if isinstance(claims, list):
        return [c.strip() for c in claims if isinstance(c, str) and c.strip()]
    if isinstance(claims, dict):
        strings = []
        for claim_data in claims.values():
            if isinstance(claim_data, dict):
                documented = (claim_data.get('documented_claim') or '').strip()
                if documented:
                    strings.append(documented)
            elif isinstance(claim_data, str) and claim_data.strip():
                strings.append(claim_data.strip())
        return strings
    return []

def _normalize_isolated_claims_for_import(isolated_claims):
    """Backfill missing claim fields so portfolio import validation can pass."""
    allowed = frozenset({
        "asserted_claim", "independent_claim", "core_claim", "pivotal_claim",
    })
    for i, claim in enumerate(isolated_claims.claims):
        if not str(claim.market_language_claim or "").strip():
            claim.market_language_claim = claim.documented_claim
        if str(claim.claim_type or "").strip().lower() not in allowed:
            claim.claim_type = "independent_claim" if i == 0 else "pivotal_claim"

def passToGeminiForMetadata(
    text: str,
    claims_content: str | None = None,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    attempt: int = 0,
    claims_mode: str = "parent",
    default_source: str = None,
    ):
    """
    Call Gemini to extract metadata and claims with simple retry/backoff.

    ``claims_mode``:
      - ``parent``: full SingleClaim dict (documented + market + claim_type) for portfolio import.
      - ``infringement_candidate``: plain list[str] of documented claims for live-search hits.
    """
    last_error: Exception | None = None
    metadata_content = str(text)
    claim_source = claims_content.strip() if claims_content and claims_content.strip() else metadata_content
    while attempt < max_attempts:
        try:
            case_data = Gemini().extract_patent_metadata(
                patent_content=metadata_content, 
                default_source=default_source
                )
            title = case_data.title
            filing_date = case_data.filingDate
            if (title.strip() == "") or (filing_date.strip() == ""):
                print(f"Error: Failed to extract patent metadata after {max_attempts} attempts. {last_error}")
                raise Exception("Error: Failed to extract patent metadata after 3 attempts")

            if claims_mode == "infringement_candidate":
                documented = Gemini().extract_documented_claims(patent_content=claim_source)
                case_data.claims = documented.claims
            else:
                isolated_claims = Gemini().extract_claims(patent_content=claim_source)
                _normalize_isolated_claims_for_import(isolated_claims)
                validated, error_message = isolated_claims.verify_isolated_claims()
                if not validated:
                    print(f"Error: Failed to extract claims after {max_attempts} attempts. {error_message}")
                    raise Exception(f"Error: Failed to extract claims after {max_attempts} attempts. {error_message}")
                final_claims = {}
                for i in range(len(isolated_claims.claims)):
                    claim = isolated_claims.claims[i]
                    final_claims[str(i)] = claim.model_dump()
                case_data.claims = final_claims
            return case_data
        except Exception as e:
            last_error = e
            attempt += 1
            if hasattr(e, 'message'):
                message = e.message
            else:
                message = str(e)
            print(f"\nLOG: Attempt {attempt} failed: {message} : {last_error}")
            if attempt >= max_attempts:
                print(f"\nMAX_ATTEMPTS_ERROR: Failed to extract patent metadata after {max_attempts} attempts")
                return None
            time.sleep(base_delay * attempt)
            return passToGeminiForMetadata(
                text=metadata_content,
                claims_content=claims_content,
                max_attempts=max_attempts,
                base_delay=base_delay,
                attempt=attempt,
                claims_mode=claims_mode,
                default_source=default_source
            )

def htmlToText(html:str, selector:str):
    soup = BeautifulSoup(html, "html.parser")
    text_content = soup.get_text(separator='\n', strip=True)
    return text_content

def performSearch(url:str, session:requests.Session = None):
    if session is None:
        session = requests.Session()
        session.headers.update(SESSION_HEADERS)
    response = session.get(url, timeout=SEARCH_TIMEOUT)
    response.raise_for_status()
    html_content = response.text
    return html_content

def fetchCaseData(url:str, session:requests.Session = None, selector:str = ''):
    if session is None:
        session = requests.Session()
        session.headers.update(SESSION_HEADERS)
    response = session.get(url, timeout=SEARCH_TIMEOUT)
    response.raise_for_status()
    html_content = response.text
    text_content = htmlToText(html_content, selector)
    return text_content

def get_case_datas(
    urlIsolatorInstance: CaseDataUrlFromSearchResults, 
    case_data_url:str, 
    session:requests.Session = None, 
    selector:str = '',
    count:int = 0):
    try:
        if 'patents.google.com' in case_data_url:
            html_content = performSearch(case_data_url, session)
            gp = GooglePatents()
            sections = gp.isolate_patent_sections(html_content)
            metadata_content = gp.content_for_metadata_extraction(sections)
            claims_content = gp.content_for_claims_extraction(sections)
            caseData = passToGeminiForMetadata(
                metadata_content,
                claims_content=claims_content,
                default_source="Google Patents",
                claims_mode="infringement_candidate",
            )
        else:
            caseDataHtml = fetchCaseData(case_data_url, session, selector)
            caseData = passToGeminiForMetadata(
                str(caseDataHtml),
                default_source="Free Patents Online",
                claims_mode="infringement_candidate",
            )
        if caseData is None:
            return None
        return caseData
    except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
        print(f"\nERROR: Connection reset error ({count + 1} of 3): {str(e)}")
        if count >= 2:  # after 3 attempts (count 0,1,2) give up
            raise e
        time.sleep(2)
        session.close()
        session = requests.Session()
        session.headers.update(SESSION_HEADERS)
        return get_case_datas(urlIsolatorInstance, case_data_url, session, selector, count + 1)
    except Exception as e:
        print(f"\nERROR: Error getting case data: {str(e)}")
        raise e

def searchFreePatentsOnline(keywords:list[str], count:int = 0):
    resultCasesList = []
    caseDataUrlsList = []
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    selector = SOURCES[0].get('url_builder_selector', '')

    try:
        freePatentsUrlBuilder = SearchUrlBuilderByKeywords(url=SOURCES[0].get('search_url', ''))
        freePatentsUrl = freePatentsUrlBuilder.build_url(
            keywords=keywords, 
            country='', 
            selector=SOURCES[0].get('url_builder_selector', '')
            )
    except Exception as e:
        print(f"\nERROR: Error building free patents online URL: {str(e)}")
        raise e
        
    try:
        session = requests.Session()
        session.headers.update(SESSION_HEADERS)
        searchResultsHtml = performSearch(freePatentsUrl, session)
        caseDataUrlIsolator = CaseDataUrlFromSearchResults(
            html_content=searchResultsHtml, 
            ids=SOURCES[0].get('search_ids', {}), 
            classes=SOURCES[0].get('search_classes', []), 
            tags=SOURCES[0].get('search_tags', {}),
            drop_list=SOURCES[0].get('search_classes_to_drop', [])
            )
        caseDataUrlsList = caseDataUrlIsolator.isolate_case_data_urls(
            selector=selector, 
            base_url=SOURCES[0].get('search_url', '')
            )
        print(f'LOG: Case Data URLs List:')
        for caseDataUrl in caseDataUrlsList:
            index = caseDataUrlsList.index(caseDataUrl)
            print(f'LOG: {index + 1}: {caseDataUrl}')
    except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
        print(f"\nERROR: Connection reset error: {str(e)}")
        if count >= 2:
            raise e
        time.sleep(2)
        session.close()
        session = requests.Session()
        session.headers.update(SESSION_HEADERS)
        return searchFreePatentsOnline(keywords, count + 1)
    except Exception as e:
        print(f"\nERROR: Error performing search for free patents online: {str(e)}")
        raise e

    print(f"Case Data URLs Length: {len(caseDataUrlsList)}")
    session.close()
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    for caseDataUrl in _tqdm(caseDataUrlsList, desc="Fetching Case Data for free patents Urls"):
        try:
            caseData = get_case_datas(caseDataUrlIsolator, caseDataUrl, session, selector)
            if caseData is None:
                print(f"\nWARN: No case data for URL: {caseDataUrl}")
                continue
            patent_id = str(caseDataUrl.split('/')[-1]).split('.')[0]
            caseDataDict = _live_result_to_dict(caseData, case_id=patent_id)
            caseDataDict['url'] = caseDataUrl
            caseDataDict['source'] = 'free_patents_online'
            resultCasesList.append(caseDataDict)
            time.sleep(DEFAULT_LLM_DELAY)
        except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
            print(f"\nERROR: Skipping URL after retries: {caseDataUrl} — {str(e)}")
        except Exception as e:
            print(f"\nERROR: Skipping URL: {caseDataUrl} — {str(e)}")
        # time.sleep(1)
    print(f'LOG: Result Cases List: {len(resultCasesList)}')
    return resultCasesList

def searchGooglePatents(keywords:list[str], count:int = 0):
    resultCasesList = []
    caseDataUrlsList = []
    selector = SOURCES[1].get('url_builder_selector', '')

    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    try:
        googlePatentsUrlBuilder = SearchUrlBuilderByKeywords(url=SOURCES[1].get('search_url', ''))
        googlePatentsUrl = googlePatentsUrlBuilder.build_url(
            keywords=keywords, 
            country='', 
            selector=SOURCES[1].get('url_builder_selector', '')
            )
    except Exception as e:
        print(f"\nERROR: Error building Google Patents URL: {str(e)}")
        raise e

    session.close()
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    try:
        searchResultsHtml = performSearch(googlePatentsUrl, session)
        caseDataUrlIsolator = CaseDataUrlFromSearchResults(
            html_content=searchResultsHtml, 
            ids=SOURCES[1].get('search_ids', {}), 
            classes=SOURCES[1].get('search_classes', []), 
            tags=SOURCES[1].get('search_tags', {}),
            drop_list=SOURCES[1].get('search_classes_to_drop', [])
            )
        caseDataUrlsList = caseDataUrlIsolator.isolate_case_data_urls(
            selector=selector, 
            base_url=SOURCES[1].get('search_url', '')
            )
        print(f'LOG: Case Data URLs List: ')
        for caseDataUrl in caseDataUrlsList:
            index = caseDataUrlsList.index(caseDataUrl)
            print(f'LOG: {index + 1}: {caseDataUrl}')
    except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
        print(f"\nERROR: Connection reset error: {str(e)}")
        if count >= 2:
            raise e
        time.sleep(2)
        session.close()
        session = requests.Session()
        session.headers.update(SESSION_HEADERS)
        return searchGooglePatents(keywords, count + 1)
    except Exception as e:
        print(f"\nERROR: Error performing search for Google Patents: {str(e)}")
        raise e
    
    print(f"Case Data URLs Length: {len(caseDataUrlsList)}")
    session.close()
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    for caseDataUrl in _tqdm(caseDataUrlsList, desc="Fetching Case Data for google patents Urls"):
        try:
            caseData = get_case_datas(caseDataUrlIsolator, caseDataUrl, session, selector)
            if caseData is None:
                print(f"\nWARN: No case data for URL: {caseDataUrl}")
                continue
            if '/en' in caseDataUrl:
                patent_id = str(caseDataUrl.split('/')[-2])
            else:
                patent_id = str(caseDataUrl.split('/')[-1])
            caseDataDict = _live_result_to_dict(caseData, case_id=patent_id)
            caseDataDict['url'] = caseDataUrl
            caseDataDict['source'] = 'google_patents'
            resultCasesList.append(caseDataDict)
            time.sleep(DEFAULT_LLM_DELAY)
        except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
            print(f"\nERROR: Skipping URL after retries: {caseDataUrl} — {str(e)}")
        except Exception as e:
            print(f"\nERROR: Skipping URL: {caseDataUrl} — {str(e)}")
        # time.sleep(1)
    print(f'LOG: Result Cases List: {resultCasesList}')
    return resultCasesList

def alreadyExists(patent:dict, merged_results:list[dict]):
    patent_id = patent.get('_id') or patent.get('case_id')
    patent_title = patent.get('title')
    for result in merged_results:
        result_id = result.get('_id') or result.get('case_id')
        if patent_id and result_id and result_id == patent_id:
            return True
        if patent_title and result.get('title') == patent_title:
            return True
        if patent.get('case_id') and result.get('case_id') == patent.get('case_id'):
            return True
        if patent.get('patent_id') and result.get('patent_id') == patent.get('patent_id'):
            return True
    return False

def performLiveSearch(
    keywords:list[str], 
    country:str, 
    ref_case_title: str = '', 
    ref_case_id: str = '',
    titles: list[str] = [],
    ids: list[str] = [],
    ):
    """
    Run live patent discovery on Free Patents Online and Google Patents, then merge
    and deduplicate results.

    Searches both sources with the given keywords. Each source's hits are filtered
    before merge so the reference case and prior hits are not returned again.

    Checks performed on each candidate result (per source):
        - Exact title match against ``titles`` (includes ``ref_case_title`` and titles
          accepted from earlier hits in this run).
        - Exact case id match against ``ids`` (includes ``ref_case_id`` and ids from
          earlier hits; case id is normalized via the last ``_`` segment).
        - Near-duplicate title via ``checkSimilarTitleExists`` (cosine similarity >
          ``TITLE_SIMILARITY_THRESHOLD``, 0.85).

    After both searches, Free Patents Online results are kept as the base list. Google
    Patents results are appended only when ``alreadyExists`` finds no duplicate by
    ``_id``, ``title``, ``case_id``, or ``patent_id`` in the merged list.

    Connection and other errors from either source are logged; the other source's
    results are still returned when possible.

    Args:
        keywords: Search terms passed to both scrapers.
        country: Reserved for scope filtering (not applied in this function yet).
        ref_case_title: Reference case title excluded from results.
        ref_case_id: Reference case id excluded from results.
        titles: Seed list of titles to skip (mutated in place as new titles are accepted).
        ids: Seed list of case ids to skip (mutated in place as new ids are accepted).

    Returns:
        list[dict]: Merged, deduplicated patent case dicts ready for infringement analysis.
    """
    free_patents_results = []
    titles.append(ref_case_title)
    ids.append(ref_case_id)
    try:
        free_patents_results = searchFreePatentsOnline(keywords)
        for result in free_patents_results:
            title = result['title'].strip()
            case_id = result.get('case_id', '').strip().split('_')[-1]
            if (title in titles) or (case_id in ids) or checkSimilarTitleExists(title, titles):
                free_patents_results.remove(result)
                continue
            titles.append(title)
            ids.append(case_id)
    except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
        print(f"\nERROR: Free Patents Online search failed after retries: {str(e)}")
    except Exception as e:
        print(f"\nERROR: Free Patents Online search failed: {str(e)}")

    google_patents_results = []
    try:
        google_patents_results = searchGooglePatents(keywords)
        for result in google_patents_results:
            title = result['title'].strip()
            case_id = result.get('case_id', '').strip().split('_')[-1]
            if (title in titles) or (case_id in ids) or checkSimilarTitleExists(title, titles):
                google_patents_results.remove(result)
                continue
            titles.append(title)
            ids.append(case_id)
    except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
        print(f"\nERROR: Google Patents search failed after retries: {str(e)}")
    except Exception as e:
        print(f"\nERROR: Google Patents search failed: {str(e)}")
    # TODO: Change to all results when new version is ready
    merged_results = list(free_patents_results)
    for patent in google_patents_results:
        if not alreadyExists(patent, merged_results):
            merged_results.append(patent)
    return merged_results

def performInfringementAnalysis(reference_claims:list[str], infringing_claims:list[str], context:str):
    infringement_analysis = Gemini().analyze_infringements(reference_claims, infringing_claims, context)
    return infringement_analysis

def alreadyExistsInProductDetailsList(product_detail, product_details_list: list):
    pid = getattr(product_detail, "product_id", None) or (product_detail.get("product_id") if isinstance(product_detail, dict) else None)
    for product in product_details_list:
        other_pid = getattr(product, "product_id", None) or (product.get("product_id") if isinstance(product, dict) else None)
        if pid and other_pid and pid == other_pid:
            return True
    return False


def _focus_urls_from_search_limitations(search_limitations: dict) -> list[str]:
    urls = []
    for entry in search_limitations.get("priority_target_sources") or []:
        if isinstance(entry, dict) and entry.get("url"):
            urls.append(entry["url"])
        elif isinstance(entry, str) and entry.strip():
            urls.append(entry.strip())
    for entry in search_limitations.get("urls") or []:
        if isinstance(entry, str) and entry.strip():
            urls.append(entry.strip())
    return list(dict.fromkeys(urls))


def _discover_products_via_gemini(
    product_name: str,
    reference_claims: list[str],
    owners: list[str],
    search_limitations: dict,
    max_product_results: int,
):
    print(
        "LOG: Gemini product search (full bucket claims; no query-generation LLM)"
    )
    google_search_results = Gemini().perform_google_search_from_claims(
        product_name=product_name,
        reference_claims=reference_claims,
        owners=owners,
        search_limitations=search_limitations,
        max_results=max_product_results,
    )
    print(f"LOG: Gemini returned {len(google_search_results)} search result(s)")
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    extracted = []
    results_to_process = google_search_results[:max_product_results]
    for result in _tqdm(
        results_to_process,
        desc="Fetching Product Details from Gemini Search Results",
    ):
        url = result.url
        try:
            html_content = performSearch(url, session)
        except (
            ConnectionResetError,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as e:
            print(f"\nERROR: Error getting HTML content for URL: {url} — {str(e)}")
            continue
        except Exception as e:
            print(f"\nERROR: Error getting HTML content for URL: {url} — {str(e)}")
            continue
        is_error_page, error_keyword = check_html_for_runtime_errors(
            html_content, url=url
        )
        if is_error_page:
            print(
                f"\nERROR: Blocked page content for URL: {url} — {error_keyword}"
            )
            continue
        try:
            product_details = Gemini().get_product_details(html_content)
        except Exception as e:
            print(f"\nERROR: Product details extraction failed for {url}: {str(e)}")
            continue
        extracted.append(product_details)

    print(f"LOG: Gemini discovery extracted {len(extracted)} product(s)")
    return extracted


def _persist_extracted_products(
    extracted_products,
    reference_claims: list[str],
    parent_case_id: str,
    product_details_list: list,
    created_ids: list,
    sites_searched: dict,
):
    for product_details in extracted_products:
        website_searched = product_details.source or "unknown"
        sites_searched[website_searched] = sites_searched.get(website_searched, 0) + 1
        try:
            infringement_analysis = Gemini().analyze_product_infringements(
                reference_claims, product_details.claims
            )
            product_details.similar_claims = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in infringement_analysis
            ]
            product_details.similar_claims = filter_similar_claims(product_details.similar_claims)
            product_id = product_details.product_id
            product_url = product_details.product_url
            print(f"LOG: Product ID: {product_id}")
            print(f"LOG: Product URL: {product_url}")
            if alreadyExistsInProductDetailsList(product_details, product_details_list):
                continue
            if (product_id is None) or (product_url is None):
                continue
            if (product_id == "") or (product_url == ""):
                continue
            if (str(product_id).lower() == "unknown") or (str(product_url).lower() == "unknown"):
                continue
            if (str(product_id).lower() == "n/a") or (str(product_url).lower() == "n/a"):
                continue
            payload = product_details.model_dump()
            payload = filter_infringement_entry(payload)
            payload["_id"] = (
                "product_"
                + str(product_id)
                + "_"
                + str(datetime.now().strftime("%Y%m%d%H%M%S"))
            )
            creation_result = infringement_model.create_infringement(
                payload,
                parent_case_id=parent_case_id or None,
            )
            if creation_result["success"]:
                created_ids.append(creation_result["infringement_id"])
            product_details_list.append(payload)
        except Exception as e:
            print(f"\nERROR: Error analyzing product infringements: {str(e)}")
            continue

# Final Search Functions

def searchPatentSources(
    keywords:list[str], 
    country:str, 
    reference_claims:list[str], 
    ref_case_title: str = '', 
    ref_case_id: str = '',
    titles_to_avoid: list[str] = [],
    ids_to_avoid: list[str] = [],
    search_type: str = 'generic',
    case_id: str = '',
    ):
    searchResults = []
    infringement_analysis_results = []
    created_ids = []
    status_key = f"{search_type}_claims_patent_analysis"
    # Perform Live Patent Search
    try:
        found_ids = []
        results = performLiveSearch(
            keywords=keywords, 
            country=country, 
            ref_case_title=ref_case_title, 
            ref_case_id=ref_case_id,
            titles=titles_to_avoid,
            ids=ids_to_avoid
            )
        for result in results:
            foundId = result.get('_id') or result.get('case_id')
            if not foundId:
                continue
            foundTitle = result.get('title', '')
            if foundId in ids_to_avoid:
                continue
            if foundTitle in titles_to_avoid:
                continue
            found_ids.append(foundId)
            searchResults.append(result)
        patent_sources = Gemini().get_patent_sources(found_ids)
        for patent in patent_sources.patents:
            for result in searchResults:
                result_id = result.get('_id') or result.get('case_id')
                if patent.id == result_id:
                    result['source'] = patent.source
                    result['country'] = patent.country
                    break
    except Exception as e:
        print(f'\nERROR: LiveSearch: Error performing live search: {str(e)}')
        case_model.update_infringement_analysis_flags(
            case_id=case_id,
            update_type='error',
            error_message='Live SearchError: ' + str(e)
        )
        raise e
    # Perform Infringement Analysis
    try:
        sources = []
        for result in searchResults:
            infringing_claims = claims_to_strings(result.get('claims', []))
            if not infringing_claims:
                print(f"\nLOG: Skipping patent {result.get('_id')} — no extractable claims")
                continue
            infringement_analysis = performInfringementAnalysis(
                reference_claims,
                infringing_claims,
                result.get('context', '') or result.get('description', '')
            )
            if hasattr(infringement_analysis, "model_dump"):
                result['gemini_infringement'] = infringement_analysis.model_dump()
            elif hasattr(infringement_analysis, "dict"):
                result['gemini_infringement'] = infringement_analysis.dict()
            else:
                result['gemini_infringement'] = infringement_analysis
            gemini_score = None
            if isinstance(result.get('gemini_infringement'), dict):
                gemini_score = result['gemini_infringement'].get('similarity_score')
            if not score_meets_threshold(gemini_score):
                result.pop('gemini_infringement', None)
            result['infringements'] = []
            result['claims'] = infringing_claims
            
            result['_id'] = 'patent_' + str(result.get('_id', '')) + '_' + str(datetime.now().strftime("%Y%m%d%H%M%S"))
            result = filter_infringement_entry(result)
            creation_result = infringement_model.create_infringement(
                result,
                parent_case_id=case_id or None,
            )
            if creation_result['success']:
                created_ids.append(creation_result['infringement_id'])
                sources.append(result.get('source', ''))
            infringement_analysis_results.append(result)
            if case_id:
                case_model.update_case(case_id, {'infringement_sources': sources})
            # TODO: Create Infringement Record after altering the id
        return infringement_analysis_results, created_ids
    except Exception as e:
        print(f'\nERROR: LiveSearch: Error performing infringement analysis: {str(e)}')
        case_model.update_infringement_analysis_flags(
            case_id=case_id,
            update_type='error',
            error_message='Live SearchError: ' + str(e)
        )
        raise e
    return [], []

def resolve_product_search_max_results(search_limitations: dict | None) -> int:
    """Max product URLs to fetch/analyze; override via search_limitations.max_product_results."""
    if not search_limitations:
        return DEFAULT_PRODUCT_SEARCH_MAX_RESULTS
    raw = search_limitations.get('max_product_results', DEFAULT_PRODUCT_SEARCH_MAX_RESULTS)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = DEFAULT_PRODUCT_SEARCH_MAX_RESULTS
    return max(1, min(n, MAX_PRODUCT_SEARCH_MAX_RESULTS))


def normalize_search_limitations(search_limitations) -> dict:
    if isinstance(search_limitations, dict):
        return dict(search_limitations)
    if isinstance(search_limitations, list):
        if search_limitations and isinstance(search_limitations[0], dict):
            return dict(search_limitations[0])
        return {}
    return {}


def resolve_product_target_sources_for_analysis(
    reference_claims: list[str],
    search_limitations: dict | None = None,
) -> dict:
    """Merge reachable default retailer URLs into search_limitations (no LLM)."""
    del reference_claims
    search_limitations = normalize_search_limitations(search_limitations)
    fallback = ProductTargetSources.default_catalog().filter_reachable()
    print(
        "LOG: Product target sources (catalog, no LLM):",
        [source.url for source in fallback.target_sources],
    )
    return fallback.merge_urls_into_search_limitations(search_limitations)


def searchProductSources(
    product_name: str,
    keywords:list[str],
    owners:list[str],
    reference_claims:list[str],
    search_limitations:dict,
    parent_case_id: str = '',
    ):
    del keywords
    search_limitations = normalize_search_limitations(search_limitations)
    max_product_results = resolve_product_search_max_results(search_limitations)
    print(f"LOG: Product search max results: {max_product_results}")
    print(f"LOG: Reference claims in bucket: {len(reference_claims or [])}")
    sites_searched = {}
    product_details_list = []
    created_ids = []
    focus_urls = _focus_urls_from_search_limitations(search_limitations)

    extracted_products = _discover_products_via_gemini(
        product_name,
        reference_claims,
        owners,
        search_limitations,
        max_product_results,
    )
    _persist_extracted_products(
        extracted_products,
        reference_claims,
        parent_case_id,
        product_details_list,
        created_ids,
        sites_searched,
    )

    if not product_details_list and is_google_custom_search_configured():
        print(
            "LOG: Gemini found no products; falling back to Google Custom Search "
            "(claim-derived terms)"
        )
        extracted_products = productGoogleSearch(
            reference_claims,
            focus_urls,
            owners=owners,
            max_results=max_product_results,
        )
        _persist_extracted_products(
            extracted_products,
            reference_claims,
            parent_case_id,
            product_details_list,
            created_ids,
            sites_searched,
        )
    elif not product_details_list:
        print("LOG: No products found via Gemini; CSE not configured")

    print(f"LOG: Product Search Sources: {json.dumps(sites_searched, indent=4)}")
    print(f"LOG: Products Found: {len(product_details_list)}")
    return product_details_list, created_ids

# New Search Functions

def searchPatentSourcesNew(
    keywords:list[str], 
    country:str, 
    reference_claims:list[str], 
    context:str):
    
    all_patent_details = []
    # TODO: Perform Live Patent Search
    try:
        # Patent Search
        google_patents = GooglePatents()
        google_patents_urls = google_patents.initial_search_results(keywords)
        print(f"LOG: Google Patents URLs({len(google_patents_urls)})")
        search_urls = []
        for data in _tqdm(google_patents_urls, desc="Fetching Google Patents Details"):
            search_urls.append(data['case_data'])
            case_details = google_patents.get_single_patent_details(data['case_data'])
            if case_details is not None:
                data['url'] = data['case_data']
                data['case_data'] = case_details
                all_patent_details.append(data)
            else:
                continue
        if len(all_patent_details) > 0:
            print(f"LOG: Google Patents Details({len(all_patent_details)})")
        else:
            print(f"LOG: Google Patents Details({len(all_patent_details)})")
        free_patents = FreePatentsOnline()
        free_patents_urls = free_patents.initial_search_results(keywords)
        print(f"LOG: Free Patents Online URLs({len(free_patents_urls)})")
        search_urls = []
        for data in _tqdm(free_patents_urls, desc="Fetching Free Patents Online Details"):
            search_urls.append(data['case_data'])
            case_details = free_patents.get_single_patent_details(data['case_data'])
            if case_details is not None:
                data['url'] = data['case_data']
                data['case_data'] = case_details
                all_patent_details.append(data)
            else:
                continue
        if len(all_patent_details) > 0:
            print(f"LOG: Free Patents Online Details({len(all_patent_details)})")
        else:
            print(f"LOG: Free Patents Online Details({len(all_patent_details)})")
        # Get Details using Gemini
        patent_details_final = []
        for data in _tqdm(all_patent_details, desc="Isolating MetaData"):
            case_details = passToGeminiForMetadata(str(data['case_data']))
            if case_details is not None:
                data.pop('case_data')
                for key, value in case_details.model_dump().items():
                    data[key] = value
                patent_details_final.append(data)
            else:
                continue
        if len(patent_details_final) > 0:
            print(f"LOG: Processed Patents with MetaData({len(patent_details_final)}) : {json.dumps(patent_details_final[0], indent=4)}")
        else:
            print(f"LOG: Processed Patents with MetaData({len(patent_details_final)})")
        return patent_details_final
        #TODO: Infringement Analysis
    except Exception as e:
        print(f'\nERROR: LiveSearch: Error performing live search: {str(e)}')
        raise e
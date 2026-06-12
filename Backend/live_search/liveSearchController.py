import time
import json
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
from file_controller import readFromXmlUrl, readFromPdfUrl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from llm_brain.gemini import Gemini
import models.infringements as infringement_model
import models.cases as case_model
from live_search.searchUrlBuilder import SearchUrlBuilderByKeywords
from live_search.caseDataUrlFromSearchResults import CaseDataUrlFromSearchResults

from web_scraper.free_patents_online import FreePatentsOnline
from web_scraper.google_patents import GooglePatents

TITLE_SIMILARITY_THRESHOLD = 0.85
SEARCH_TIMEOUT = 10
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


def _model_to_dict(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _analysis_to_plain_list(value):
    plain = _model_to_dict(value)
    if isinstance(plain, list):
        return [_model_to_dict(item) for item in plain]
    if isinstance(plain, dict):
        for key in ("similar_claims", "claims", "matches", "infringements"):
            nested = plain.get(key)
            if isinstance(nested, list):
                return [_model_to_dict(item) for item in nested]
        return [plain] if plain else []
    return _as_list(plain)


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url or "").netloc.replace("www.", "")
    except Exception:
        return ""


def _fallback_product_id(product_details: dict, url: str, index: int) -> str:
    raw_id = product_details.get("product_id") or product_details.get("id")
    if raw_id and str(raw_id).strip().lower() not in {"unknown", "n/a", "none"}:
        return str(raw_id).strip()
    name = product_details.get("product_name") or product_details.get("name") or product_details.get("title") or "product"
    safe_name = "_".join(str(name).lower().split())[:60] or "product"
    domain = _domain_from_url(url).replace(".", "_") or "source"
    return f"{domain}_{safe_name}_{index + 1}"


def _normalize_patent_infringement(result: dict, infringement_analysis, parent_case_id: str) -> dict:
    payload = dict(result or {})
    analysis_list = _analysis_to_plain_list(infringement_analysis)
    payload["infringements"] = analysis_list
    payload["similar_claims"] = analysis_list
    payload["infringement_type"] = "patent"
    payload["type"] = "patent"
    payload["parent_case_id"] = parent_case_id
    payload["entry_id"] = payload.get("entry_id") or payload.get("case_id") or payload.get("patent_id") or payload.get("_id")
    payload["entry_title"] = payload.get("entry_title") or payload.get("title") or "Patent infringement source"
    payload["entry_url"] = payload.get("entry_url") or payload.get("url") or payload.get("source_url") or ""
    return payload


def _normalize_product_infringement(product_details, infringement_analysis, source_result, parent_case_id: str, index: int) -> dict:
    payload = _model_to_dict(product_details)
    url = payload.get("product_url") or payload.get("url") or getattr(source_result, "url", "")
    product_id = _fallback_product_id(payload, url, index)
    analysis_list = _analysis_to_plain_list(infringement_analysis)
    payload.update({
        "product_id": product_id,
        "product_url": url,
        "infringement_type": "product",
        "type": "product",
        "parent_case_id": parent_case_id,
        "entry_id": product_id,
        "entry_title": payload.get("product_name") or payload.get("name") or payload.get("title") or "Product infringement source",
        "entry_url": url,
        "source": getattr(source_result, "website_name", None) or _domain_from_url(url) or payload.get("source") or "Product Source",
        "similar_claims": analysis_list,
        "infringements": analysis_list,
    })
    return payload

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

def _live_result_to_dict(obj):
    """Convert LiveSearchResults (or similar) to a JSON-serializable dict for API and alreadyExists()."""
    if obj is None:
        return None
    if hasattr(obj, 'model_dump'):
        d = obj.model_dump()
    elif hasattr(obj, 'dict'):
        d = obj.dict()
    else:
        return obj
    if isinstance(d.get('claims'), dict) and 'claims' in d['claims']:
        d['claims'] = d['claims']['claims']
    return d

def passToGeminiForMetadata(text: str, max_attempts: int = 3, base_delay: float = 2.0, attempt: int = 0):
    """
    Call Gemini to extract metadata and claims with simple retry/backoff.
    Retries on transient errors (including 5xx) up to max_attempts times.
    """
    last_error: Exception | None = None
    while attempt < max_attempts:
        try:
            case_data = Gemini().extract_patent_metadata(patent_content=str(text))
            title = case_data.title
            filing_date = case_data.filingDate
            if (title.strip() == "") or (filing_date.strip() == ""):
                raise Exception("Error: Failed to extract patent metadata after 3 attempts")

            # Extract claims as a separate model, then attach just the list.
            isolated_claims = Gemini().extract_claims(patent_content=str(text))
            try:
                claims_list = getattr(isolated_claims, "claims", [])
                if isinstance(claims_list, list):
                    if len(claims_list) <3:
                        raise Exception("ClaimsError: Claims not properly isolated")
            except Exception:
                claims_list = []
            case_data.claims = claims_list
            return case_data
        except Exception as e:
            last_error = e
            attempt += 1
            if hasattr(e, 'message'):
                message = e.message
            else:
                message = str(e)
            print(f"\nLOG: Attempt {attempt} failed: {message}")
            # If we've exhausted retries, re-raise
            if attempt >= max_attempts:
                print(f"\nMAX_ATTEMPTS_ERROR: Failed to extract patent metadata after {max_attempts} attempts")
                return None
            # Basic backoff between retries
            time.sleep(base_delay * attempt)
            passToGeminiForMetadata(str(text), max_attempts, base_delay, attempt)

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
        caseDataHtml = fetchCaseData(case_data_url, session, selector)
        caseData = passToGeminiForMetadata(str(caseDataHtml))
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
    for caseDataUrl in tqdm(caseDataUrlsList, desc="Fetching Case Data for free patents Urls"):
        try:
            caseData = get_case_datas(caseDataUrlIsolator, caseDataUrl, session, selector)
            caseDataDict = _live_result_to_dict(caseData)
            caseDataDict['case_id'] = str(caseDataUrl.split('/')[-1]).split('.')[0]
            caseDataDict['url'] = caseDataUrl
            caseDataDict['source'] = 'free_patents_online'
            resultCasesList.append(caseDataDict)
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
    for caseDataUrl in tqdm(caseDataUrlsList, desc="Fetching Case Data for google patents Urls"):
        try:
            caseData = get_case_datas(caseDataUrlIsolator, caseDataUrl, session, selector)
            caseDataDict = _live_result_to_dict(caseData)
            if '/en' in caseDataUrl:
                caseDataDict['case_id'] = str(caseDataUrl.split('/')[-2])
            else:
                caseDataDict['case_id'] = str(caseDataUrl.split('/')[-1])
            caseDataDict['url'] = caseDataUrl
            caseDataDict['source'] = 'google_patents'
            resultCasesList.append(caseDataDict)
        except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
            print(f"\nERROR: Skipping URL after retries: {caseDataUrl} — {str(e)}")
        except Exception as e:
            print(f"\nERROR: Skipping URL: {caseDataUrl} — {str(e)}")
        # time.sleep(1)
    print(f'LOG: Result Cases List: {resultCasesList}')
    return resultCasesList

def alreadyExists(patent:dict, merged_results:list[dict]):
    for result in merged_results:
        if result['_id'] == patent['_id']:
            return True
        if result['title'] == patent['title']:
            return True
        if result['case_id'] == patent['case_id']:
            return True
        if result['patent_id'] == patent['patent_id']:
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

# Final Search Functions

def searchPatentSources(
    keywords:list[str], 
    country:str, 
    reference_claims:list[str], 
    ref_case_title: str = '', 
    ref_case_id: str = '',
    titles_to_avoid: list[str] = [],
    ids_to_avoid: list[str] = [],
    parent_case_id: str = '',
    ):
    searchResults = []
    infringement_analysis_results = []
    created_ids = []
    # Perform Live Patent Search
    try:
        found_ids = []
        results = performLiveSearch(
            keywords, 
            country=country, 
            ref_case_title=ref_case_title, 
            ref_case_id=ref_case_id,
            titles=titles_to_avoid,
            ids=ids_to_avoid,
            )
        for result in results:
            found_ids.append(result['_id'])
            searchResults.append(result)
        patent_sources = Gemini().get_patent_sources(found_ids)
        for patent in patent_sources.patents:
            for result in searchResults:
                if patent.id == result['_id']:
                    result['source'] = patent.source
                    result['country'] = patent.country
                    break
    except Exception as e:
        print(f'\nERROR: LiveSearch: Error performing live search: {str(e)}')
        raise e
    # Perform Infringement Analysis
    try:
        sources = []
        for result in searchResults:
            infringement_analysis = performInfringementAnalysis(
                reference_claims,
                result.get('claims', []),
                result.get('context', '')
            )
            result = _normalize_patent_infringement(result, infringement_analysis, parent_case_id or result.get('parent_case_id') or result.get('case_id'))
            result['_id'] = 'patent_' + str(result.get('entry_id') or result.get('_id')) + '_' + str(datetime.now().strftime("%Y%m%d%H%M%S"))
            creation_result = infringement_model.create_infringement(result, parent_case_id=parent_case_id or result.get('parent_case_id'))
            if creation_result['success']:
                created_ids.append(creation_result['infringement_id'])
                if result.get('source'):
                    sources.append(result['source'])
            else:
                print(f"\nERROR: Failed to store patent infringement: {creation_result.get('message')}")
            infringement_analysis_results.append(result)
            if parent_case_id:
                case_model.update_case(parent_case_id, {'infringement_sources': sources})
            # TODO: Create Infringement Record after altering the id
        return infringement_analysis_results, created_ids
    except Exception as e:
        print(f'\nERROR: LiveSearch: Error performing infringement analysis: {str(e)}')
        raise e
    return [], []

def searchProductSources(keywords:list[str], owners:list[str], reference_claims:list[str], search_limitations:dict, parent_case_id: str = ''):
    # Generate Search String using Gemini
    search_string = Gemini().get_search_string(keywords, owners, search_limitations)
    print(f"LOG: Search String: {search_string}")
    # Perform Google Search
    google_search_results = Gemini().perform_google_search(search_string)
    sites_searched = {}
    product_details_list = []
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    created_ids = []
    # TODO: Change to all results when new version is ready
    # Iterate through Google Search Results
    for result in tqdm(google_search_results[:10], desc="Fetching Product Details from Google Search Results"):
        website_searched = result.website_name
        if website_searched not in sites_searched.keys():
            sites_searched[website_searched] = 0
        sites_searched[website_searched] += 1
        url = result.url
        # Get HTML Content for each URL from search results
        try:
            html_content = performSearch(url, session)
        except (ConnectionResetError, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            print(f"\nERROR: Error getting HTML content for URL: {url} — {str(e)}")
            continue
        except Exception as e:
            print(f"\nERROR: Error getting HTML content for URL: {url} — {str(e)}")
            continue
        # Pass HTML Content to Gemini to extract product details
        product_details = Gemini().get_product_details(html_content)
        # Analyze Product Infringements
        try:
            infringement_analysis = Gemini().analyze_product_infringements(reference_claims, product_details.claims)
            product_payload = _normalize_product_infringement(product_details, infringement_analysis, result, parent_case_id, len(product_details_list))
            product_id = product_payload.get('product_id')
            product_url = product_payload.get('product_url')
            print(f"LOG: Product ID: {product_id}")
            print(f"LOG: Product URL: {product_url}")
            if alreadyExistsInProductDetailsList(product_payload, product_details_list):
                continue
            if not product_url or str(product_url).strip().lower() in {"unknown", "n/a", "none"}:
                continue
            product_payload['_id'] = 'product_' + str(product_id) + '_' + str(datetime.now().strftime("%Y%m%d%H%M%S"))
            creation_result = infringement_model.create_infringement(product_payload, parent_case_id=parent_case_id)
            if creation_result['success']:
                created_ids.append(creation_result['infringement_id'])
            else:
                print(f"\nERROR: Failed to store product infringement: {creation_result.get('message')}")
            product_details_list.append(product_payload)
        except Exception as e:
            print(f"\nERROR: Error analyzing product infringements: {str(e)}")
            continue
    print(f"LOG: Product Search Sources: {json.dumps(sites_searched, indent=4)}")
    print(f"LOG: Products Found: {len(product_details_list)}")
    return product_details_list, created_ids

# New Search Functions

def searchPatentSourcesNew(keywords:list[str], country:str, reference_claims:list[str], context:str):
    searchResults = []
    infringement_analysis_results = []

    all_patent_details = []
    # TODO: Perform Live Patent Search
    try:
        # Patent Search
        google_patents = GooglePatents()
        google_patents_urls = google_patents.initial_search_results(keywords)
        print(f"LOG: Google Patents URLs({len(google_patents_urls)})")
        search_urls = []
        for data in tqdm(google_patents_urls, desc="Fetching Google Patents Details"):
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
        for data in tqdm(free_patents_urls, desc="Fetching Free Patents Online Details"):
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
        for data in tqdm(all_patent_details, desc="Isolating MetaData"):
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
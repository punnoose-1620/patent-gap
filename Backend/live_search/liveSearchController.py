import time
import json
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
from file_controller import readFromXmlUrl, readFromPdfUrl

from llm_brain.gemini import Gemini
from live_search.searchUrlBuilder import SearchUrlBuilderByKeywords
from live_search.caseDataUrlFromSearchResults import CaseDataUrlFromSearchResults

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
        'details_class_to_isolate': [],
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

def passToGeminiForMetadata(text: str, max_attempts: int = 3, base_delay: float = 2.0):
    """
    Call Gemini to extract metadata and claims with simple retry/backoff.
    Retries on transient errors (including 5xx) up to max_attempts times.
    """
    attempt = 0
    last_error: Exception | None = None
    while attempt < max_attempts:
        try:
            case_data = Gemini().extract_patent_metadata(patent_content=text)
            title = case_data.title
            filing_date = case_data.filingDate
            if (title.strip() == "") or (filing_date.strip() == ""):
                raise Exception("Error: Failed to extract patent metadata after 3 attempts")

            # Extract claims as a separate model, then attach just the list.
            isolated_claims = Gemini().extract_claims(patent_content=text)
            try:
                claims_list = getattr(isolated_claims, "claims", [])
            except Exception:
                claims_list = []
            case_data.claims = claims_list
            return case_data
        except Exception as e:
            last_error = e
            attempt += 1
            # If we've exhausted retries, re-raise
            if attempt >= max_attempts:
                raise
            # Basic backoff between retries
            time.sleep(base_delay * attempt)

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
        caseData = passToGeminiForMetadata(caseDataHtml)
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
            resultCasesList.append(_live_result_to_dict(caseData))
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
            resultCasesList.append(_live_result_to_dict(caseData))
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

def performLiveSearch(keywords:list[str], country:str):
    free_patents_results = []
    try:
        free_patents_results = searchFreePatentsOnline(keywords)
    except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
        print(f"\nERROR: Free Patents Online search failed after retries: {str(e)}")
    except Exception as e:
        print(f"\nERROR: Free Patents Online search failed: {str(e)}")

    google_patents_results = []
    try:
        google_patents_results = searchGooglePatents(keywords)
    except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
        print(f"\nERROR: Google Patents search failed after retries: {str(e)}")
    except Exception as e:
        print(f"\nERROR: Google Patents search failed: {str(e)}")

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

def searchPatentSources(keywords:list[str], country:str, reference_claims:list[str]):
    searchResults = []
    infringement_analysis_results = []
    # Perform Live Patent Search
    try:
        results = performLiveSearch(keywords, country=country)
        for result in results:
            searchResults.append(result)
    except Exception as e:
        print(f'\nERROR: LiveSearch: Error performing live search: {str(e)}')
        raise e
    # Perform Infringement Analysis
    try:
        for result in searchResults:
            infringement_analysis = performInfringementAnalysis(
                ref_claims,
                result.get('claims', []),
                result.get('context', '')
            )
            # Convert Pydantic model to plain dict so Flask/jsonify can serialize it
            if hasattr(infringement_analysis, "model_dump"):
                infringement_dict = infringement_analysis.model_dump()
            elif hasattr(infringement_analysis, "dict"):
                infringement_dict = infringement_analysis.dict()
            else:
                infringement_dict = infringement_analysis
            infringement_analysis_results.append(infringement_dict)
        return infringement_analysis_results
    except Exception as e:
        print(f'\nERROR: LiveSearch: Error performing infringement analysis: {str(e)}')
        raise e
    return []

def searchProductSources(keywords:list[str], owners:list[str], reference_claims:list[str]):
    # Generate Search String using Gemini
    search_string = Gemini().get_search_string(keywords, owners)
    print(f"LOG: Search String: {search_string}")
    # Perform Google Search
    google_search_results = Gemini().perform_google_search(search_string)
    sites_searched = {}
    product_details_list = []
    # Iterate through Google Search Results
    for result in tqdm(google_search_results, desc="Fetching Product Details from Google Search Results"):
        website_searched = result.website_name
        if website_searched not in sites_searched.keys():
            sites_searched[website_searched] = 0
        sites_searched[website_searched] += 1
        url = result.url
        # Get HTML Content for each URL from search results
        try:
            session = requests.Session()
            session.headers.update(SESSION_HEADERS)
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
            product_details.similar_claims = infringement_analysis
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
            if (str(product_id).lower() == "unknown") or (str(product_url).lower == "unknown"):
                continue
            if (str(product_id).lower() == "n/a") or (str(product_url).lower() == "n/a"):
                continue
            product_details_list.append(product_details)
        except Exception as e:
            print(f"\nERROR: Error analyzing product infringements: {str(e)}")
            continue
    print(f"LOG: Product Search Sources: {json.dumps(sites_searched, indent=4)}")
    print(f"LOG: Products Found: {len(product_details_list)}")
    return product_details_list
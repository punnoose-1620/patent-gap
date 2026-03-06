import requests
from bs4 import BeautifulSoup
from searchUrlBuilder import SearchUrlBuilderByKeywords
from file_controller import readFromXmlUrl, readFromPdfUrl
from caseDataUrlFromSearchResults import CaseDataUrlFromSearchResults

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
    }
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

def passToGemini(text:str):
    print()
    return {}

def converHtmlToText(html:str, selector:str):
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

def fetchCaseData(url:str, session:requests.Session = None):
    if session is None:
        session = requests.Session()
        session.headers.update(SESSION_HEADERS)
    response = session.get(url, timeout=SEARCH_TIMEOUT)
    response.raise_for_status()
    html_content = response.text
    text_content = converHtmlToText(html_content, selector)
    return text_content

def searchFreePatentsOnline(keywords:list[str]):
    resultCasesList = []
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    freePatentsUrlBuilder = SearchUrlBuilderByKeywords(url=SOURCES[0]['search_url'])
    freePatentsUrl = freePatentsUrlBuilder.build_url(
        keywords=keywords, 
        country='', 
        selector=SOURCES[0]['url_builder_selector']
        )
    searchResultsHtml = performSearch(freePatentsUrl, session)
    caseDataUrlIsolator = CaseDataUrlFromSearchResults(
        html_content=searchResultsHtml, 
        ids=SOURCES[0]['search_ids'], 
        classes=SOURCES[0]['search_classes'], 
        tags=SOURCES[0]['search_tags'],
        drop_list=SOURCES[0]['search_classes_to_drop']
        )
    caseDataUrlsList = caseDataUrlIsolator.isolate_case_data_urls(selector=SOURCES[0]['url_builder_selector'])
    for caseDataUrl in caseDataUrlsList:
        caseDataHtml = fetchCaseData(caseDataUrl, session)
        caseDataText = converHtmlToText(caseDataHtml, selector)
        caseData = passToGemini(caseDataText)
        resultCasesList.append(caseData)
    return resultCasesList

def searchGooglePatents(keywords:list[str]):
    resultCasesList = []
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    googlePatentsUrlBuilder = SearchUrlBuilderByKeywords(url=SOURCES[1]['search_url'])
    googlePatentsUrl = googlePatentsUrlBuilder.build_url(
        keywords=keywords, 
        country='', 
        selector=SOURCES[1]['url_builder_selector']
        )
    searchResultsHtml = performSearch(googlePatentsUrl, session)
    caseDataUrlIsolator = CaseDataUrlFromSearchResults(
        html_content=searchResultsHtml, 
        ids=SOURCES[1]['search_ids'], 
        classes=SOURCES[1]['search_classes'], 
        tags=SOURCES[1]['search_tags'],
        drop_list=SOURCES[1]['search_classes_to_drop']
        )
    caseDataUrlsList = caseDataUrlIsolator.isolate_case_data_urls(selector=SOURCES[1]['url_builder_selector'])
    for caseDataUrl in caseDataUrlsList:
        caseDataHtml = fetchCaseData(caseDataUrl, session)
        caseDataText = converHtmlToText(caseDataHtml, selector)
        caseData = passToGemini(caseDataText)
        resultCasesList.append(caseData)
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
    free_patents_results = searchFreePatentsOnline(keywords)
    google_patents_results = searchGooglePatents(keywords)
    merged_results = free_patents_results
    for patent in google_patents_results:
        if patent not alreadyExists(patent, merged_results):
            merged_results.append(patent)
    return merged_results
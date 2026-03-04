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
    # For each case data, fetch case data html content
    # Convert html content to string
    # Pass to Gemini for detail extraction
    print()

def searchGooglePatents(keywords:list[str]):
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)
    # Construct the URL
    # Perform the search and get list html
    # Isolate Case Data Urls from result html
    # For each case data, fetch case data html content
    # Convert html content to string
    # Pass to Gemini for detail extraction
    print()

def performLiveSearch(keywords:list[str], country:str):
    # Perform live search on Free Patents Online and get list1
    # Perform live search on Google Patents and get list2
    # Merge list 1 and list 2 without duplicates. Use ID for checking. 
    # Use fuzzy checking on titles and add 'duplicate_warning' boolean flage if >0.8 similarity score
    # Return the merged list
    print()
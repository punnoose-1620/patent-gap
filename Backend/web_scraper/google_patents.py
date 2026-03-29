import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from web_scraper.web_scraper import WebScraper

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

class GooglePatents:
    base_url: str
    scraper: WebScraper
    session: requests.Session
    ids_to_isolate: list[str]
    classes_to_drop:list[str]

    def __init__(self):
        self.base_url = 'https://patents.google.com'
        self.session = requests.Session()
        self.session.headers.update(SESSION_HEADERS)
        self.session.timeout = SEARCH_TIMEOUT
        self.scraper = WebScraper(session=self.session)
        self.classes_to_drop = ['header', 'pageFooter']
        self.ids_to_isolate = ['wrapper']

    def __url_builder(self, keywords:list[str]):
        keywords_merged = "+".join(keywords)
        keywords_merged = keywords_merged.replace(' ', '+')

        q_value = f"q=({keywords_merged})"
        oq_value = f"oq={keywords_merged}"
        page_limit = 'num=5000'

        search_url = f'{self.base_url}/?{q_value}&{page_limit}&{oq_value}'
        print(f"Google Patents Search Url : {search_url}")
        return search_url
        
    def __id_search1_url_builder(self, search_id:str):
        metaData_Url = f'{self.base_url}/xhr/parse?text={search_id}'
        metaData = self.session.get(metaData_Url)
        # Expected response: {
        #   "results": [
        #     {
        #       "result": {
        #         "id": "/patent/US1234567890/en",
        #         "number": "1234567890",
        #         "title": "Patent Title"
        #       }
        #     }
        #   ]
        # }
        if metaData.status_code != 200:
            return None
        metaData = metaData.json()
        # Get Search MetaData
        if metaData is None or metaData.get('results') is None:
            return None
        metaData_results = metaData.get('results')
        if len(metaData_results) == 0:
            return None
        metaData_result = metaData_results[0]
        if metaData_result is None:
            return None
        metaData_result = metaData_result.get('result')
        if metaData_result is None:
            return None
        url_mid_section = metaData_result.get('id')
        if url_mid_section is None or url_mid_section == '':
            return self.scraper.resolve_url(self.base_url, search_id)
        # Find Final Search URL
        url = urljoin(self.base_url, url_mid_section+"?oq="+search_id)
        if url is None:
            return None
        
        return url

    def __isolate_search_tags(self, html: str):
        """
        Isolate search tags from the search results page.
        Input: HTML string from search results page.
        Output: List of HTML strings (isolated html content of each search tag).
        """
        # Find all search results using article tag
        isolated_search_content = []
        soup = BeautifulSoup(html, 'html.parser')
        article_tags = soup.find_all('article')

        for article_tag in tqdm(article_tags, desc="GooglePatents: Isolating search tags"):
            # Find Title from each result
            a_tag = article_tag.find('a')
            href = a_tag.get('href')
            resolved_url = self.scraper.resolve_url(self.base_url, href)
            title = a_tag.find('span').get_text(strip=True)
            # Find and isolate patent id
            patent_id_tag = article_tag.find('span', attrs={'data-proto': 'OPEN_PATENT_PDF'})
            patent_id = patent_id_tag.get_text(strip=True)
            # Find all owner tags (might contain owning firm/company names, but all use same formatting - cannot differentiate)
            owner_tags = article_tag.find_all('span', id='htmlContent', class_='style-scope raw-html')
            owners = []
            for owner_tag in owner_tags:
                owners.append(owner_tag.get_text(strip=True))

            search_data = {
                'url': resolved_url,
                'title': title,
                'patent_id': patent_id,
                'owners': owners
            }
            isolated_search_content.append(search_data)
        return isolated_search_content

    def __isolate_case_data_by_id(self, html: str):
        """
        Isolate case data by id from the case details page.
        Input: HTML string from case details page.
        Output: List of HTML strings (isolated html content of each case data).
        """
        isolated_case_data = []
        soup = BeautifulSoup(html, 'html.parser')
        isolated_content = soup.find(id='wrapper')
        claims = isolated_content.find('text').get_text(strip=True)
        return {
            'case_data': isolated_content,
            'claims': claims
        }

    def initial_search_results(self, keywords:list[str]):
        """
        Get initial search results from Google Patents.
        Input: List of keywords.
        Output: List of URLs from search results.
        """
        search_url = self.__url_builder(keywords)
        html = self.scraper.get(search_url)
        
        search_results = self.__isolate_search_tags(html)
        return search_results

    def get_single_patent_details(self, url: str):
        """
        Fetch patent-detail page for the provided URL.
        Input: String URL.
        Output: HTML string (isolated html content of the case details page).
        """
        try:
            html = self.scraper.get(url)
            if html is not None:
                return self.__isolate_case_data_by_id(html)
            else:
                print(f"ERROR: Failed to fetch patent details from {url}: {str(html)}")
                return None
        except requests.RequestException as e:
            print(f"ERROR: Failed to fetch patent details from {url}: {str(e)}")
            return None
        except Exception as e:
            print(f"ERROR: Failed to fetch patent details from {url}: {str(e)}")
            return None

    def search_by_id(self, search_id:str):
        """
        Search by ID from Google Patents.
        Input: String ID.
        Output: HTML string (isolated html content of the case details page).
        """
        url = self.__id_search1_url_builder(search_id)
        if url is None:
            return None
        
        try:
            html = self.scraper.get(url)
            if html is not None:
                return str(html)
            else:
                print(f"ERROR: Failed to fetch patent details from {url}")
                return str(html)
        except requests.RequestException as e:
            print(f"ERROR: Failed to fetch patent details from {url}: {str(e)}")
            return None
        # TODO: Isolate case data from html using gemini

    def get_patent_details(self, urls: list[str]):
        """
        Get patent details from Google Patents.
        Input: List of URLs.
        Output: List of patent details.
        Output Format: {
            'case_data': HTML string (isolated html content of case data),
            'claims': HTML string (isolated html content of claims)
        }
        """
        patent_details = []
        for url in urls:
            if not url:
                continue
            try:
                html = self.scraper.get(url)
                if html is not None:
                    processed_html = self.__isolate_case_data_by_id(html)
                    patent_details.append(processed_html)
            except requests.RequestException as e:
                print(f"ERROR: Failed to fetch patent details from {url}: {str(e)}")
                continue
        return patent_details
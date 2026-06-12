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

    def __section_text(self, soup: BeautifulSoup, itemprop: str) -> str:
        section = soup.find('section', attrs={'itemprop': itemprop})
        if section is None:
            return ''
        return section.get_text(separator='\n', strip=True)

    def isolate_patent_sections(self, html: str) -> dict:
        """
        Extract structured text sections from a Google Patents detail page.
        Current pages use itemprop sections instead of the legacy #wrapper layout.
        """
        soup = BeautifulSoup(html, 'html.parser')
        sections = {
            'metadata': self.__section_text(soup, 'metadata'),
            'application': self.__section_text(soup, 'application'),
            'abstract': self.__section_text(soup, 'abstract'),
            'description': self.__section_text(soup, 'description'),
            'claims': self.__section_text(soup, 'claims'),
        }
        # Legacy layout fallback
        if not sections['claims']:
            wrapper = soup.find(id='wrapper')
            if wrapper is not None:
                text_el = wrapper.find('text')
                if text_el is not None:
                    sections['claims'] = text_el.get_text(separator='\n', strip=True)
        return sections

    def content_for_metadata_extraction(self, sections: dict, max_description_chars: int = 80000) -> str:
        description = sections.get('description', '') or ''
        if len(description) > max_description_chars:
            description = (
                description[:max_description_chars]
                + "\n\n...[description truncated for metadata extraction]..."
            )
        parts = [
            ('Metadata', sections.get('metadata', '')),
            ('Application', sections.get('application', '')),
            ('Abstract', sections.get('abstract', '')),
            ('Description', description),
        ]
        return '\n\n'.join(f"{label}:\n{text}" for label, text in parts if text.strip())

    def content_for_claims_extraction(self, sections: dict) -> str:
        claims = (sections.get('claims') or '').strip()
        if claims:
            return f"Patent Claims:\n{claims}"
        description = (sections.get('description') or '').strip()
        if description:
            return f"Patent Description (claims section not found; search for claims):\n{description}"
        return ''

    def __isolate_case_data_by_id(self, html: str):
        """
        Isolate case data by id from the case details page.
        Input: HTML string from case details page.
        Output: dict with isolated metadata text and claims text.
        """
        sections = self.isolate_patent_sections(html)
        return {
            'case_data': self.content_for_metadata_extraction(sections),
            'claims': sections.get('claims', ''),
            'sections': sections,
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

    def get_patent_page_url(self, search_id: str) -> str | None:
        return self.__id_search1_url_builder(search_id)

    def search_by_id(self, search_id:str):
        """
        Search by ID from Google Patents.
        Input: String ID.
        Output: dict with metadata_content and claims_content for Gemini extraction.
        """
        url = self.__id_search1_url_builder(search_id)
        if url is None:
            return None
        
        try:
            html = self.scraper.get(url)
            if html is None:
                print(f"ERROR: Failed to fetch patent details from {url}")
                return None
            sections = self.isolate_patent_sections(html)
            metadata_content = self.content_for_metadata_extraction(sections)
            claims_content = self.content_for_claims_extraction(sections)
            if not metadata_content.strip() and not claims_content.strip():
                print(f"ERROR: No isolatable patent content from {url}")
                return None
            return {
                'metadata_content': metadata_content,
                'claims_content': claims_content,
                'sections': sections,
            }
        except requests.RequestException as e:
            print(f"ERROR: Failed to fetch patent details from {url}: {str(e)}")
            return None

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
import json
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
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

class FreePatentsOnline:
    base_url: str
    scraper: WebScraper
    session: requests.Session
    search_tags:dict[str, str]
    classes_to_isolate:list[str]

    def __init__(self):
        self.base_url = 'https://www.freepatentsonline.com/result.html'
        self.session = requests.Session()
        self.session.headers.update(SESSION_HEADERS)
        self.session.timeout = SEARCH_TIMEOUT
        self.scraper = WebScraper(session=self.session)
        # TODO: Add ids, classes, and tags to isolate and drop
        self.classes_to_isolate = ['fixed-width document-details-wrapper']
        self.search_tags = {
            'case_data': 'a',
            'patent_id': 'td-1',
            'title': 'td-2'
        }

    def __id_url_builder(self, id:str):
        return f'{self.base_url}?sort=relevance&srch=top&query_txt={id}'

    def __isolate_id_search_results(self, html: str):
        """
        Isolate search results from the search results page.
        Input: HTML string from search results page.
        Output: List of HTML strings (isolated html content of each search tag).
        """
        isolated_search_content = {}
        soup = BeautifulSoup(html, 'html.parser')
        # Find all TR entries
        table_rows = soup.find_all('tr')
        if len(table_rows) < 2:
            return None
        # Get the 2nd TR entry (first is headings)
        top_result = table_rows[2]
        if top_result is None:
            return None
        top_result_tds = top_result.find_all('td')
        if len(top_result_tds) < 4:
            return None

        id_td = top_result_tds[1]
        score_td = top_result_tds[3]
        title_td = top_result_tds[2].find('a').get_text(strip=True)
        url_td = top_result_tds[2].find('a').get('href')
        url = self.scraper.resolve_url(self.base_url, url_td)
        briefDescription = top_result_tds[2].get_text(strip=True).split("&nbsp;")[-1].strip().replace(title_td, '').strip()
        search_data = {
            'patent_id': id_td.get_text(strip=True),
            'score': score_td.get_text(strip=True),
            'title': title_td,
            'url': url,
            'briefDescription': briefDescription
        }
        return search_data

    def __url_builder(self, keywords:list[str]):
        sort_param = 'sort=relevance'
        keywords_merged = ''
        keywords_merged = "+".join(keywords)
        keywords_merged = keywords_merged.replace(' ', '+')

        search_url = f'{self.base_url}?{sort_param}&query_txt={keywords_merged}'
        
        print(f"Free Patents Online Search Url : {search_url}")
        return search_url

    def __isolate_search_tags(self, html: str):
        """
        Isolate search tags from the search results page.
        Input: HTML string from search results page.
        Output: List of HTML strings (isolated html content of each search tag).
        """
        isolated_search_content = []
        soup = BeautifulSoup(html, 'html.parser')
        """
        Expected table entry format:
        Match Number | Patent ID | Title [url] & Brief Description
        """
        table_rows = soup.find_all('tr')
        for el in tqdm(table_rows, desc="FreePatentsOnline: Isolating search tags"):
            search_data = {}
            tds = el.find_all('td')
            # If there are less than 3 tds, skip the entry
            if len(tds) < 4:
                continue
            patent_id = tds[1].get_text(strip=True)
            title = tds[2].find('a').get_text(strip=True)
            case_data = tds[2].find('a').get('href')
            briefDescription = tds[2].get_text(strip=True).split("&nbsp;")[-1].strip().replace(title, '').strip()
            search_data = {
                'patent_id': patent_id,
                'title': title,
                'case_data': self.scraper.resolve_url(self.base_url, case_data),
                'briefDescription': briefDescription
            }

            isolated_search_content.append(search_data)
        print(f"LOG: FreePatentsLiveSearch: Isolated {len(isolated_search_content)} search results")
        return isolated_search_content

    def __isolate_case_data_by_class(self, html: str):
        """
        Isolate case data by class from the case details page.
        Input: HTML string from case details page.
        Output: List of HTML strings (isolated html content of each case data).
        """
        isolated_case_data = []
        soup = BeautifulSoup(html, 'html.parser')
        for el in soup.find_all(class_='fixed-width document-details-wrapper'):
            isolated_case_data.append(str(el))
        return isolated_case_data

    def search_by_id(self, id:str):
        """
        Search by ID from Free Patents Online.
        Input: String ID.
        Output: HTML string (isolated html content of the case details page).
        """
        search_url = self.__id_url_builder(id)
        html = self.scraper.get(search_url)
        if html is not None:
            isolated_base_data = self.__isolate_id_search_results(html)
            if isolated_base_data is None:
                return None
            url = isolated_base_data.get('url')
            if url is None:
                return None
            new_html = self.scraper.get(url)
            if new_html is None:
                return None
            isolated_case_data = self.__isolate_case_data_by_class(new_html)
            if isolated_case_data is None:
                return None
            return isolated_case_data
        else:
            print(f"ERROR: Failed to fetch patent details from {search_url}: {str(html)}")
        return None

    # TODO: Isolate case data from html using gemini

    def initial_search_results(self, keywords:list[str]):
        """
        Get initial search results from Free Patents Online.
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
                return self.__isolate_case_data_by_class(html)
            else:
                print(f"ERROR: Failed to fetch patent details from {url}: {str(html)}")
                return None
        except requests.RequestException as e:
            print(f"ERROR: Failed to fetch patent details from {url}: {str(e)}")
            return None
        except Exception as e:
            print(f"ERROR: Failed to fetch patent details from {url}: {str(e)}")
            return None

    def get_patent_details(self, urls: list[str]):
        """
        Fetch patent-detail pages for the provided URLs.
        Uses the shared scraper session and returns the HTML response for each
        successfully fetched URL, preserving input order. If class filters are
        configured, only matching sections are kept and wrapped in a root div.
        Input: List of String URLs.
        Output: List of HTML strings (isolated html content of each case details page).
        """
        patent_details = []
        for url in urls:
            if not url:
                continue
            try:
                html = self.scraper.get(url)
                if html is not None:
                    # Isolate content by class from case details page content
                    html = self.__isolate_case_data_by_class(html)
                    patent_details.append(html)
            except requests.RequestException as e:
                print(f"ERROR: Failed to fetch patent details from {url}: {str(e)}")
                continue
        return patent_details
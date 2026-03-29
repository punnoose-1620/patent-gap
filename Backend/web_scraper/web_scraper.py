import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class WebScraper:
    session: requests.Session
    
    def __init__(self, session: requests.Session = None, headers: dict = None, timeout: int = 10):
        if session is None:
            self.session = requests.Session()
        else:
            self.session = session
        if headers is not None:
            self.session.headers.update(headers)
        self.timeout = timeout
    
    def get(self, url: str, params: dict = None):
        response = self.session.get(url, params=params)
        return response.text
    
    def isolate_content_by_id(self, html: str, ids: list[str]):
        soup = BeautifulSoup(html, 'html.parser')
        isolated_content = []
        for _id in ids:
            if _id is None:
                # Return HTML so the remove_* pipeline can safely parse/decompose.
                return [str(soup)]
            for el in soup.find_all(id=_id):
                # Keep markup (not .text) so later remove_* calls can remove ids/classes/tags.
                isolated_content.append(str(el))
        return isolated_content

    def isolate_content_by_class(self, html: str, classes: list[str]):
        soup = BeautifulSoup(html, 'html.parser')
        isolated_content = []
        for _class in classes:
            if _class is None:
                # Return HTML so the remove_* pipeline can safely parse/decompose.
                return [str(soup)]
            for el in soup.find_all(class_=_class):
                # Keep markup (not .text) so later remove_* calls can remove ids/classes/tags.
                isolated_content.append(str(el))
        return isolated_content

    def isolate_search_tags(self, html: str, tags: dict[str, str]):
        soup = BeautifulSoup(html, 'html.parser')
        isolated_content = []
        
        for tag, _class in tags.items():
            if _class is None:
                continue
            for el in soup.find_all(tag, class_=_class):
                isolated_content.append(str(el))
        return isolated_content

    def isolate_content_by_tag(self, html: str, tags: list[str]):
        soup = BeautifulSoup(html, 'html.parser')
        isolated_content = []
        for _tag in tags:
            if _tag is None:
                # Return HTML so the remove_* pipeline can safely parse/decompose.
                return [str(soup)]
            # BeautifulSoup uses the tag name as the "name" selector (positional arg),
            # so we should not pass it via a `tag=` keyword.
            for el in soup.find_all(_tag):
                # Keep markup (not .text) so later remove_* calls can remove ids/classes/tags.
                isolated_content.append(str(el))
        return isolated_content

    def remove_ids(self, html: str, ids: list[str]):
        soup = BeautifulSoup(html, 'html.parser')
        for id in ids:
            if id is None:
                continue
            for el in soup.find_all(id=id):
                el.decompose()
        return str(soup)

    def remove_classes(self, html: str, classes: list[str]):
        soup = BeautifulSoup(html, 'html.parser')
        for _class in classes:
            if _class is None:
                continue
            for el in soup.find_all(class_=_class):
                el.decompose()
        return str(soup)

    def remove_tags(self, html: str, tags: list[str]):
        soup = BeautifulSoup(html, 'html.parser')
        for tag in tags:
            if tag is None:
                continue
            for el in soup.find_all(tag):
                el.decompose()
        return str(soup)

    def resolve_url(self, base_url: str, path: str):
        if not path:
            return base_url
        if path.startswith('//'):
            return 'https:' + path
        return urljoin(base_url, path)
import json
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup

class CaseDataUrlFromSearchResults:
  html_content:str
  ids:list
  classes:list
  tags:dict

  def __init__(self, html_content:str, ids:list, classes:list, tags:dict, drop_list: list[str]):
    self.html_content = self.drop_elements_by_classes(html_content, drop_list)
    self.ids = ids
    self.classes = classes
    self.tags = tags
 
  def converHtmlToText(self, html:str, selector:str):
    soup = BeautifulSoup(html, "html.parser")
    text_content = soup.get_text(separator='\n', strip=True)
    return text_content

  def url_checker(self, url:str):
    returnVal = False
    if 'http' in url:
        returnVal = True
    if 'https' in url:
        returnVal = True
    if 'www' in url:
        returnVal = True
    if '//' in url:
        returnVal = True
    if 'http://' in url:
        returnVal = True
    if 'https://' in url:
        returnVal = True
    return returnVal

  def resolve_url(self, href:str, base:str, selector:str):
    if self.url_checker(href):
        return href
    if selector == 'google-patents':
        return base + href
    else:
        return base.replace('/result.html', '') + href
    return base + href

  def isolate_case_data_urls(self, selector:str, base_url:str):
    urls = []
    if selector == 'free-patents-online':
        urls_by_ids = self.get_entries_by_id(base_url=base_url, selector=selector)                  # Returns list of urls
        urls_by_classes = self.get_entries_by_class(base_url=base_url, selector=selector)           # Returns list of urls
        urls_by_tags = self.get_entries_by_tag_freePatents(base_url=base_url, selector=selector)    # Returns list of dicts
        urls = urls_by_ids
        for url in urls_by_classes:
            if url not in urls:
                urls.append(url)
        for entry in urls_by_tags:
            url = entry['case_data']
            if url not in urls and url is not None:
                urls.append(url)
    elif selector == 'google-patents':
        urls_by_ids = self.get_entries_by_id(base_url=base_url, selector=selector)                  # Returns list of urls
        urls_by_classes = self.get_entries_by_class(base_url=base_url, selector=selector)           # Returns list of urls
        urls_by_tags = self.get_entries_by_tag_googlePatents(base_url=base_url, selector=selector)  # Returns list of links
        urls = urls_by_ids
        for url in urls_by_classes:
            if url not in urls:
                urls.append(url)
        for url in urls_by_tags:
            if url not in urls:
                urls.append(url)
    return urls

  def drop_elements_by_classes(self, html_content:str, drop_list: list[str]):
    soup = BeautifulSoup(html_content, "html.parser")
    for class_name in drop_list:
        for tag in soup.find_all(class_=class_name):
            tag.decompose()
    return str(soup)

  def get_entries_by_id(self, base_url:str, selector:str):
    resultList = []
    if len(self.ids)==0:
      return []
    soup = BeautifulSoup(self.html_content, "html.parser")

    for id in self.ids:
        tag = soup.find(id=id)
        if tag:
            url = tag.get('href')
            url = self.resolve_url(url, base_url, selector)
            resultList.append(url)
    return resultList

  def get_entries_by_class(self, base_url:str, selector:str):
    resultList = []
    if len(self.classes)==0:
      return []
    soup = BeautifulSoup(self.html_content, "html.parser")

    for classname in self.classnames:
        tags = soup.find_all(class_=classname)
        for tag in tags:
            if tag:
                url = tag.get('href')
                url = self.resolve_url(url, base_url, selector)
                resultList.append(url)
    return resultList

  def get_entries_by_tag_freePatents(self, base_url:str, selector:str):
    resultList = []
    soup = BeautifulSoup(self.html_content, "html.parser")
    for td in soup.find_all("td"):
      entry = {}
      for data_key, tag in self.tags.items():
        found = td.find(tag)
        if found:
            content = found.get_text(strip=True)
            url = found.get('href')
            if url is not None:
                url = self.resolve_url(url, base_url, selector)
                entry[data_key] = url
            else:
                entry[data_key] = content
      if entry:
            resultList.append(entry)
    return resultList

  def get_entries_by_tag_googlePatents(self, base_url:str, selector:str):
    resultList = []
    soup = BeautifulSoup(self.html_content, "html.parser")
    for link in soup.find_all('link'):
      url = link.get('href')
      url = self.resolve_url(url, base_url, selector)
      resultList.append(url)
    return resultList
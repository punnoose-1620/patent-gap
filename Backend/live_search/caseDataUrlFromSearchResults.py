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

  def isolate_case_data_urls(self, selector:list[str]):
    # TODO
    # Isolate Case Data Urls using ids, classes and tags. 
    # Merge all results into a single list
    # Return merged list
    print()

  def drop_elements_by_classes(self, drop_list: list[str]):
    soup = BeautifulSoup(self.html_content, "html.parser")
    for class_name in drop_list:
        for tag in soup.find_all(class_=class_name):
            tag.decompose()
    return str(soup)

  def get_entries_by_id(self):
    resultList = []
    if len(self.ids)==0:
      return []
    soup = BeautifulSoup(self.html_content, "html.parser")

    for id in self.ids:
        tag = soup.find(id=id)
        if tag:
            resultList.append(tag)

    return resultList

  def get_entries_by_class(self):
    resultList = []
    if len(self.classes)==0:
      return []
    soup = BeautifulSoup(self.html_content, "html.parser")

    for classname in self.classnames:
        tags = soup.find_all(class_=classname)
        for tag in tags:
            if tag:
                resultList.append(tag)

    return resultList

  def get_entries_by_tag_freePatents(self):
    resultList = []
    soup = BeautifulSoup(self.html_content, "html.parser")
    for td in soup.find_all("td"):
      entry = {}
      for data_key, tag in self.tags.items():
        found = td.find(tag)
        if found:
            entry[data_key] = found.get_text(strip=True)
      if entry:
            resultList.append(entry)
    return resultList

  def get_entries_by_tag_googlePatents(self):
    resultList = []
    soup = BeautifulSoup(self.html_content, "html.parser")
    return resultList
  
  def drop_elements_by_classes(self, classes: list[str]):
    soup = BeautifulSoup(self.html_content, "html.parser")
    for class_name in classes:
        for tag in soup.find_all(class_=class_name):
            tag.decompose()
    return str(soup)
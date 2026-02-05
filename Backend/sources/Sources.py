import json
import os

class Sources:

    def getRemainingSources(self):
        file_path = os.path.join(os.path.dirname(__file__), "remaining_sources.json")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    def getUnifiedSources(self):
        file_path = os.path.join(os.path.dirname(__file__), "unified_sources.json")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    
    def isSourceIntegrated(self, source_title):
        unified_sources = self.getUnifiedSources()
        for source in unified_sources:
            if source_title == source['title']:
                return True
        return False

    def getCoveredJurisdictions(self):
        jurisdictions = []
        unified_sources = self.getUnifiedSources()
        for source in unified_sources:
            sourceJurisdictions = source['jurisdiction']
            for item in sourceJurisdictions:
                if item not in jurisdictions:
                    jurisdictions.append(item)
        return jurisdictions
    
    def getIntegratedSourceTitles(self):
        source_titles = []
        unified_sources = self.getUnifiedSources()
        for source in unified_sources:
            source_titles.append(source['title'])
        return source_titles
    
    def getSearchUrlWithQuery(self, title:str, keywords:list[str], country:str):
        unified_sources = self.getUnifiedSources()
        for source in unified_sources:
            if source['title'] == title:
                base_url = str(source['sample_search']).split("/?")[0]
                queryKeys = source['query_keys']
                countryString = f"&country={country}"
                for key in queryKeys:
                    if key != 'country':
                        base_url += f"&{key}={keywords.join('+')}"
                    if key == 'country':
                        base_url += countryString
                return base_url
        return None
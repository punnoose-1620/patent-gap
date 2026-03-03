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

def performSearch(url:str):
    # Perform fetch for url search results and get html content
    # Return html content
    print()


def searchFreePatentsOnline(keywords:list[str]):
    # Construct the URL
    # Perform the search and get list html
    # Isolate Case Data Urls from result html
    # For each case data, fetch case data html content
    # Convert html content to string
    # Pass to Gemini for detail extraction
    print()

def searchGooglePatents(keywords:list[str]):
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
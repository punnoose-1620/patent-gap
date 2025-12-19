import io
import os
import ast
import json
import uuid
import PyPDF2
import openai
import requests
import datetime
import numpy as np
from tqdm import tqdm
from env_controller import getEnvKey
from models.cases import get_case_embedding, create_case, get_case_by_id, update_case
from database import updateDataById
from llm_processor import getCompleteReport, getReportSummary, getDummyReportWithSummary
from file_controller import readDocumentFromUrl
from sklearn.feature_extraction.text import TfidfVectorizer
from sources.USPTO import USPTOPatentAPI, MissingAPIKeyError

# Module-level variable to store USPTO API instance
_uspto_api_instance = None

def initialize_uspto_api():
    """
    Initialize the USPTO Patent API client using the API key from environment variables.
    The instance is stored as a module-level variable for reuse.
    
    Returns:
        USPTOPatentAPI: The initialized USPTO API client instance
        
    Raises:
        MissingAPIKeyError: If USPTO_API_KEY is not set in environment variables
        
    Example:
        >>> api = initialize_uspto_api()
        >>> results = api.search_patents("Utility", limit=10)
    """
    global _uspto_api_instance
    
    # Get API key from environment
    api_key = getEnvKey('uspto')
    
    if not api_key:
        raise MissingAPIKeyError(
            "USPTO_API_KEY environment variable is not set.\n"
            "Please add USPTO_API_KEY=your-api-key to your .env file.\n"
            "Get your API key at: https://account.uspto.gov/api-manager/"
        )
    
    # Initialize if not already initialized
    if _uspto_api_instance is None:
        _uspto_api_instance = USPTOPatentAPI(api_key=api_key)
    
    return _uspto_api_instance

def get_uspto_api():
    """
    Get the USPTO API client instance. Initializes it if not already initialized.
    
    Returns:
        USPTOPatentAPI: The USPTO API client instance
    """
    global _uspto_api_instance
    
    if _uspto_api_instance is None:
        return initialize_uspto_api()
    
    return _uspto_api_instance

def extract_keywords_from_documents(document_urls, top_n=15):
    """
    Reads the content from a list of document URLs and isolates an array of relevant keywords.

    Args:
        document_urls (list): List of URLs/paths to documents (PDFs or text files).
        top_n (int): Number of top keywords to extract from each document (default 15).

    Returns:
        dict: Mapping of each document URL to its list of extracted keywords.
    """
    def fetch_text_from_url(url):
        # If URL is a http/https path, fetch and (if PDF, extract text)
        # If it's a local file path, open and read contents
        if url.startswith("http"):
            try:
                response = requests.get(url)
                response.raise_for_status()
                # Basic guess: PDF if endswith .pdf, else treat as text
                if url.lower().endswith('.pdf'):
                    reader = PyPDF2.PdfReader(io.BytesIO(response.content))
                    text = ''
                    for page in reader.pages:
                        text += page.extract_text() or ""
                    return text
                else:
                    return response.text
            except Exception as e:
                print(f"Could not fetch {url}: {e}")
                return ""
        else:
            # Local file
            try:
                if url.lower().endswith('.pdf'):
                    return readDocumentFromUrl(url)
                else:
                    with open(url, 'r', encoding='utf-8') as f:
                        return f.read()
            except Exception as e:
                print(f"Could not open {url}: {e}")
                return ""

    results = {}
    for doc_url in document_urls:
        text = fetch_text_from_url(doc_url)
        if not text or len(text) < 25:
            results[doc_url] = []
            continue

        # Use TF-IDF to extract keywords
        try:
            # Split into sentences for vectorizer
            documents = [text]
            vectorizer = TfidfVectorizer(
                stop_words='english', 
                lowercase=True, 
                ngram_range=(1,2), 
                max_features=1000
            )
            X = vectorizer.fit_transform(documents)
            indices = X[0].toarray().argsort()[0][::-1]
            feature_names = vectorizer.get_feature_names_out()

            # Get top keywords by TF-IDF score
            keywords = []
            sorted_indices = X[0].toarray()[0].argsort()[::-1]
            for idx in sorted_indices[:top_n]:
                keywords.append(feature_names[idx])
            results[doc_url] = keywords
        except Exception as e:
            print(f"TF-IDF failed on {doc_url}: {e}")
            results[doc_url] = []

    return results

def getKeywordsFromContentOnline(content, api_key=None, model="gpt-3.5-turbo"):
    """
    Extract keywords from `content` using the OpenAI API.
    Args:
        content (str): The text to extract keywords from.
        api_key (str, optional): OpenAI API key; if not provided, uses OPENAI_API_KEY environment var.
    Returns:
        list: List of extracted keyword strings.
    """
    if content is None:
        return []
    api_key = api_key or os.getenv('OPENAI_API_KEY')
    client = openai.OpenAI(api_key=api_key)

    prompt = (
        "Extract the most important, domain-specific keywords from the following text. "
        "Only output a Python list of keywords as strings, no explanations or comments.\n\n"
        f"Text:\n{content}\n\nKeywords:"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert assistant that extracts keywords as a Python list."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=128,
        )
        raw = response.choices[0].message.content.strip()
        # Safely evaluate Python list string to actual list
        keywords = ast.literal_eval(raw)
        if not isinstance(keywords, list):
            return []
        # Ensure all keywords are strings and deduped
        keywords = [str(k).strip() for k in keywords if isinstance(k, str)]
        return keywords
    except Exception as e:
        print(f"OpenAI keyword extraction failed: {e}")
        return []

def getKeywordsFromContentOffline(content):
    """
    Extract keywords from `content` using TF-IDF.
    Args:
        content (str): The text to extract keywords from.
    Returns:
        list: List of top keyword strings.
    """
    # Treat the content as a single document; TF-IDF needs at least one doc
    if content is None:
        return []
    docs = [content]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=20)
    tfidf_matrix = vectorizer.fit_transform(docs)
    feature_names = vectorizer.get_feature_names_out()
    scores = tfidf_matrix.toarray()[0]

    # Get indices of top N scores
    N = 10
    top_indices = np.argsort(scores)[::-1][:N]
    keywords = [feature_names[i] for i in top_indices if scores[i] > 0]

    return keywords

def getKeywordsFromContent(content, api_key=None, model="gpt-3.5-turbo"):
    """
    Extract keywords from `content` using both online and offline methods.
    Args:
        content (str): The text to extract keywords from.
    Returns:
        list: List of top keyword strings.
    """
    if content is None:
        return []
    if api_key is not None:
        try:
            return getKeywordsFromContentOnline(content, api_key, model)
        except Exception as e:
            print(f"OpenAI keyword extraction failed: {e}")
            return getKeywordsFromContentOffline(content)
    else:
        return getKeywordsFromContentOffline(content)

def getReferenceFromNormalizedList(listOfCases, case_id):
    """
    Given a list of normalized case dictionaries (`listOfCases`) and a `case_id`,
    this function compiles a list of reference dictionaries. Each reference includes
    its URL, title, granted (filing) date, and a similarity score computed by comparing
    the embedding for `case_id` to the document embeddings within each case.
    """
    listOfReferences = []
    case_embedding = get_case_embedding(case_id)
    for case in listOfCases:
        if case is not None:
            # If documents exist as a key and is a non-empty array
            if ('documents' in case.keys()) and (case.get('documents') is not None) and (len(case.get('documents')) > 0):
                url = case.get('documents')[0].get('url')
                title = case.get('title')
                granted_date = case.get('filing_date')
                similarity_rate = None
                referenceEmbeddings = case.get('document_embedding')
                if (referenceEmbeddings is not None) and (len(referenceEmbeddings) > 0):
                    similarity_rate = getSimilarityScore(case_embedding, referenceEmbeddings)
                    listOfReferences.append({
                        'url': url,
                        'title': title,
                        'granted_date': granted_date,
                        'similarity_rate': similarity_rate
                    })
    return listOfReferences

def getReferenceFromUSPTOResults(result, document_url, similarity_rate):
    title = None
    granted_date = None

    try:
        applicationMetaData = result.get('applicationMetaData')

        if applicationMetaData is not None:
            title = applicationMetaData.get('inventionTitle')
            granted_date = applicationMetaData.get('applicationStatusDate')
    except Exception as e:
        print(f'Error in getReferenceFromUSPTOResults: {e}')
    return {
        'url': document_url,
        'title': title,
        'granted_date': granted_date,
        'similarity_rate': similarity_rate
    }

def getSimilarityScoresFromUSPTOResults(results):
    listWithEmbeddings = []
    for result in results:
        if (result.get('document_embedding') is not None) and (len(result.get('document_embedding')) > 0):
            listWithEmbeddings.append(result)
    
    print('listWithEmbeddings: ', len(listWithEmbeddings), '\n')
    try: 
        # for result in listWithEmbeddings:
        for result in tqdm(listWithEmbeddings, desc='Processing similarity scores'):
            listOfEmbeddings = []
            listOfIds = []
            listWithoutResult = listWithEmbeddings.copy()
            listWithoutResult.remove(result)

            for otherResult in listWithoutResult:
                listOfEmbeddings.append(otherResult.get('document_embedding'))
                listOfIds.append(otherResult.get('_id'))
            # Calculate similarity scores between the result and the other results
            similarity_scores = getBulkSimilarityScore(result.get('document_embedding'), listOfEmbeddings)
            # Add the references to the result
            print('similarity_scores: ', len(similarity_scores), '\n')
            for i in range(len(similarity_scores)):
                # Get the reference from the other result
                if 'document_urls' in result.keys():
                    reference = getReferenceFromUSPTOResults(result, result.get('document_urls')[0].get('url'), similarity_scores[i])
                    print('reference: ', reference, '\n')
                    if listWithEmbeddings[i].get('references') is not None:
                        if listWithEmbeddings[i]['references'] is None:
                            listWithEmbeddings[i]['references'] = []
                    listWithEmbeddings[i]['references'].append(reference)
        
        for result in results:
            for updatedResult in listWithEmbeddings:
                if updatedResult.get('_id') == result.get('_id'):
                    result = updatedResult
                if results.index(result) == 0:
                    print('result: ', json.dumps(result, indent=4), '\n')
    except Exception as e:
        print(f'Error in getSimilarityScoresFromUSPTOResults: {e}')
    return results

def isolateDataFromUSPTOResults(result):
    """
    This function extracts key structured information from a raw USPTO API result dictionary.
    - From the `eventDataBag` list, it collects all eventCode, eventDescriptionText, and eventDate for each event.
    - From the `applicationMetaData`, it pulls core application fields such as applicationStatusCode, applicationTypeCode, entityStatusData, filingDate, inventorBag (with full name and correspondenceAddressBag), applicationStatusDescriptionText, inventionTitle, firstInventorName, etc.
    - It checks for existence of nested keys before extracting values; if some keys are missing, their values may be set as None or skipped.
    - From the `parentContinuityBag`, it extracts all parent continuation application relationships, collecting fields like parentApplicationStatusCode, claimParentageTypeCode, and parentApplicationNumberText, if present.
    - The function also takes top-level fields such as lastIngestionDateTime if available.
    The extraction is performed conditionally depending on the presence of sections and keys in the result dictionary to ensure robust handling of incomplete or malformed data.

    Structure of Result Input:
        result
        |-> eventDataBag: list of dictionaries
        |   |-> eventCode: string
        |   |-> eventDescriptionText: string
        |   |-> eventDate: Date (YYYY-MM-DD)
        |-> applicationMetaData: dictionary
        |   |-> applicationStatusCode: number
        |   |-> applicationTypeCode: string
        |   |-> entityStatusData: dictionary
        |   |   |-> smallEntityStatusIndicator: boolean
        |   |   |-> businessEntityStatusCategory: string
        |   |-> filingDate: Date (YYYY-MM-DD)
        |   |-> inventorBag: list of dictionaries
        |   |   |-> firstName: string
        |   |   |-> lastName: string
        |   |   |-> inventorNameText: string
        |   |   |-> correspondenceAddressBag: list of dictionaries
        |   |   |   |-> cityName: string
        |   |   |   |-> geographicRegionName: string
        |   |   |   |-> geographicRegionCode: string
        |   |   |   |-> countryCode: string
        |   |   |   |-> NameLineOneText: string
        |   |   |   |-> countryName: string
        |   |   |   |-> postalAddressCategory: string
        |   |-> applicationStatusDescriptionText: string
        |   |-> customerNumber: number
        |   |-> groupArtUnitNumber: number
        |   |-> inventionTitle: string
        |   |-> nationalStageIndicator: boolean
        |   |-> firstInventorName: string
        |   |-> applicationConfirmationNumber: number
        |   |-> effectiveFilingDate: Date (YYYY-MM-DD)
        |   |-> applicationTypeLabelName: string
        |   |-> publicationCategoryBag: list of strings
        |   |-> applicationStatusDate: Date (YYYY-MM-DD)
        |   |-> class: number
        |   |-> docketNumber: string
        |   |-> applicationTypeCategory: string
        |-> parentContinuityBag: list of dictionaries
        |   |-> parentApplicationStatusCode: number
        |   |-> fifrstInventorToFileIndicator: boolean
        |   |-> claimParentageTypeCode: string
        |   |-> claimParentageTypeCodeDescriptionText: string
        |   |-> parentApplicationStatusDescriptionText: string
        |   |-> parentApplicationNumberText: number
        |   |-> parentApplicationFilingDate: Date (YYYY-MM-DD)
        |   |-> childApplicationNumberText: number
        |   |-> parentpatentNumber: number
        |-> lastIngestionDateTime : DateTime(YYYY-MM-DDTHH:MM:SS.sssZ)
        |-> recordAttorney : dictionary
        |   |-> powerOfAttorneyBag: list of dictionaries
        |   |   |-> activeIndicator: string
        |   |   |-> firstName: string
        |   |   |-> lastName: string
        |   |   |-> registrationNumber: string
        |   |   |-> attorneyAddressBag: list of dictionaries
        |   |   |   |-> cityName: string
        |   |   |   |-> geographicRegionName: string
        |   |   |   |-> geographicRegionCode: string
        |   |   |   |-> countryCode: string
        |   |   |   |-> postalCode: number
        |   |   |   |-> nameLineOneText: string
        |   |   |   |-> countryName: string
        |   |   |   |-> addressLineOneText: string
        |   |   |   |-> addressLineTwoText: string
        |   |   |-> telecommunicationAddressBag: list of dictionaries
        |   |   |   |-> telecommunicationNumber: string
        |   |   |   |-> telecommunicationType: string
        |-> attorneyBag: list of dictionaries
        |-> applicationNumberText : number
        |-> correspondenceAddressBag: list of dictionaries
        |   |-> cityName
        |   |-> geographicRegionName
        |   |-> geographicRegionCode
        |   |-> countryCode
        |   |-> postalCode
        |   |-> nameLineOneText
        |   |-> countryName
        |   |-> addressLineOneText
        |   |-> addressLineTwoText
    """
    def processAddressLineText(address):
        address['addressLineText'] = ''
        if 'nameLineOneText' in address.keys():
            if address['nameLineOneText'] is not None:
                address['addressLineText'] = address.pop('nameLineOneText')
        if 'addressLineOneText' in address.keys():
            if address['addressLineOneText'] is not None:
                address['addressLineText'] = address['addressLineText'] + ',' + address.pop('addressLineOneText')
        if 'addressLineTwoText' in address.keys():
            if address['addressLineTwoText'] is not None:
                address['addressLineText'] = address['addressLineText'] + ',' + address.pop('addressLineTwoText')
        return address

    applicationNumber = None
    titleData = None
    descriptionData = None
    currentStatusData = None
    currentStatusCode = None
    currentStatusDate = None
    attorneys = []
    inventors = []
    mailingAddresses = []
    filingUser = None
    filingDate = None
    try:
        correspondenceAddressBag = result.get('correspondenceAddressBag')
        recordAttorney = result.get('recordAttorney')
        applicationMetaData = result.get('applicationMetaData')

        if result.get('applicationNumberText') is not None:
            applicationNumber = f"uspto_{result.get('applicationNumberText')}"
        else:
            applicationNumber = f"uspto_{uuid.uuid4().hex}"

        if applicationMetaData is not None:
            titleData = applicationMetaData.get('inventionTitle')
            filingDate = applicationMetaData.get('filingDate')
            tempInventors = applicationMetaData.get('inventorBag')
            currentStatusCode = applicationMetaData.get('applicationStatusCode')
            currentStatusDate = applicationMetaData.get('applicationStatusDate')
            currentStatusData = applicationMetaData.get('applicationStatusDescriptionText')
            if type(tempInventors) is list:
                for inventor in tempInventors:
                    inventors.append(inventor.get('inventorNameText'))
                tempInventorAddresses = inventor.get('correspondenceAddressBag')
                if type(tempInventorAddresses) is list:
                    for address in tempInventorAddresses:
                        mailingAddresses.append(processAddressLineText(address))
        if type(correspondenceAddressBag) is list:
            for address in correspondenceAddressBag:
                mailingAddresses.append(processAddressLineText(address))
        # From recordAttorney, get the power of attorney name, registration number & contact numbers
        # Append attorney address to mailing address (if active attorney)
        if recordAttorney is not None:
            powerOfAttorney = recordAttorney.get('powerOfAttorneyBag')
            if type(powerOfAttorney) is list:
                for tempAttorney in powerOfAttorney:
                    # Only consider active attorneys
                    if tempAttorney.get('activeIndicator') in ['ACTIVE', 'active']:
                        addressBag = tempAttorney.get('attorneyAddressBag')
                        if type(addressBag) is list:
                            for address in addressBag:
                                mailingAddresses.append(processAddressLineText(address))
                        communicationBag = tempAttorney.get('telecommunicationAddressBag')
                        contactNumbers = []
                        for communication in communicationBag:
                            contactNumbers.append(communication.get('telecommunicationNumber'))
                        attorneys.append({
                            'name': tempAttorney.get('firstName') + ' ' + tempAttorney.get('lastName'),
                            'registrationNumber': tempAttorney.get('registrationNumber'),
                            'contact': contactNumbers
                        })

        finalResult = {
            '_id': applicationNumber,
            'title': titleData,
            'status': currentStatusData,
            'description': descriptionData,
            'currentStatusCode': currentStatusCode,
            'currentStatusDate': currentStatusDate,
            'attorneys': attorneys,    # Name, Registration Number, Contact
            'inventors': inventors,    # List of names
            'mailingAddresses': mailingAddresses,  # cityName, geographicRegionName, geographicRegionCode, countryCode, postalCode, addressLineText
            'created_by': filingUser,
            'created_date': datetime.datetime.utcnow().isoformat(),
            'filing_date': filingDate,
            'references': []  # list of dictionaries with url, title, granted_date, similarity_rate
        }
        return finalResult
    except Exception as e:
        print(f'Error in isolateDataFromUSPTOResults: {e}')
        return None

def getKeywordDocumentsUSPTO(keywords:list[str], load_to_database:bool = False):
    """
    Retrieve all relevant documents and patent applications from the USPTO API that are associated with the specified keywords. 
    The function initializes or uses an existing USPTO API client, constructs a keyword-based OR search query, and requests up to 100 matching patent records from the API. 
    It returns the results as a structured dictionary containing meta-data, event histories, application data, inventors, attorneys, and additional patent information for each relevant document.

    Args:
        keywords: List of keywords or a single keyword string

    Structure of Results:
        results
        |-> count: number
        |-> patentFileWrapperDataBag: list of dictionaries
        |   |-> eventDataBag: list of dictionaries
        |   |   |-> eventCode: string
        |   |   |-> eventDescriptionText: string
        |   |   |-> eventDate: Date (YYYY-MM-DD)
        |   |-> applicationMetaData: dictionary
        |   |   |-> applicationStatusCode: number
        |   |   |-> applicationTypeCode: string
        |   |   |-> entityStatusData: dictionary
        |   |   |   |-> smallEntityStatusIndicator: boolean
        |   |   |   |-> businessEntityStatusCategory: string
        |   |   |-> filingDate: Date (YYYY-MM-DD)
        |   |   |-> inventorBag: list of dictionaries
        |   |   |   |-> firstName: string
        |   |   |   |-> lastName: string
        |   |   |   |-> inventorNameText: string
        |   |   |   |-> correspondenceAddressBag: list of dictionaries
        |   |   |   |   |-> cityName: string
        |   |   |   |   |-> geographicRegionName: string
        |   |   |   |   |-> geographicRegionCode: string
        |   |   |   |   |-> countryCode: string
        |   |   |   |   |-> NameLineOneText: string
        |   |   |   |   |-> countryName: string
        |   |   |   |   |-> postalAddressCategory: string
        |   |   |-> applicationStatusDescriptionText: string
        |   |   |-> customerNumber: number
        |   |   |-> groupArtUnitNumber: number
        |   |   |-> inventionTitle: string
        |   |   |-> nationalStageIndicator: boolean
        |   |   |-> firstInventorName: string
        |   |   |-> applicationConfirmationNumber: number
        |   |   |-> effectiveFilingDate: Date (YYYY-MM-DD)
        |   |   |-> applicationTypeLabelName: string
        |   |   |-> publicationCategoryBag: list of strings
        |   |   |-> applicationStatusDate: Date (YYYY-MM-DD)
        |   |   |-> class: number
        |   |   |-> docketNumber: string
        |   |   |-> applicationTypeCategory: string
        |   |-> parentContinuityBag: list of dictionaries
        |   |   |-> parentApplicationStatusCode: number
        |   |   |-> fifrstInventorToFileIndicator: boolean
        |   |   |-> claimParentageTypeCode: string
        |   |   |-> claimParentageTypeCodeDescriptionText: string
        |   |   |-> parentApplicationStatusDescriptionText: string
        |   |   |-> parentApplicationNumberText: number
        |   |   |-> parentApplicationFilingDate: Date (YYYY-MM-DD)
        |   |   |-> childApplicationNumberText: number
        |   |   |-> parentpatentNumber: number
        |   |-> lastIngestionDateTime : DateTime(YYYY-MM-DDTHH:MM:SS.sssZ)
        |   |-> recordAttorney : dictionary
        |   |   |-> powerOfAttorneyBag: list of dictionaries
        |   |   |   |-> activeIndicator: string
        |   |   |   |-> firstName: string
        |   |   |   |-> lastName: string
        |   |   |   |-> registrationNumber: string
        |   |   |   |-> attorneyAddressBag: list of dictionaries
        |   |   |   |   |-> cityName: string
        |   |   |   |   |-> geographicRegionName: string
        |   |   |   |   |-> geographicRegionCode: string
        |   |   |   |   |-> countryCode: string
        |   |   |   |   |-> postalCode: number
        |   |   |   |   |-> nameLineOneText: string
        |   |   |   |   |-> countryName: string
        |   |   |   |   |-> addressLineOneText: string
        |   |   |   |   |-> addressLineTwoText: string
        |   |   |   |-> telecommunicationAddressBag: list of dictionaries
        |   |   |   |   |-> telecommunicationNumber: string
        |   |   |   |   |-> telecommunicationType: string
        |   |   |-> attorneyBag: list of dictionaries
        |   |-> applicationNumberText : number
        |   |-> correspondenceAddressBag: list of dictionaries
        |   |   |-> cityName
        |   |   |-> geographicRegionName
        |   |   |-> geographicRegionCode
        |   |   |-> countryCode
        |   |   |-> postalCode
        |   |   |-> nameLineOneText
        |   |   |-> countryName
        |   |   |-> addressLineOneText
        |   |   |-> addressLineTwoText
        |-> requestIdentifier
    
    Returns:
        Dictionary containing search results with patents matching any of the keywords
        |-> applicationNumber: string
        |-> title: string
        |-> currentStatus: string
        |-> currentStatusCode: number
        |-> currentStatusDate: Date (YYYY-MM-DD)
        |-> attorneys: list of dictionaries
        |-> inventors: list of strings
        |-> mailingAddresses: list of dictionaries
        |-> filingDate: Date (YYYY-MM-DD)
        |-> document_urls: list of dictionaries
        |   |-> source: string
        |   |-> url: string
        |-> keywords: list of strings
    """
    # Use the module-level instance if available, otherwise initialize it
    global _uspto_api_instance
    
    if _uspto_api_instance is None:
        api = get_uspto_api()
    else:
        api = _uspto_api_instance
    
    # Merge keywords using OR operator
    query = " OR ".join(keywords)
    
    # Search for patents matching the query
    results = api.search_patents(query=query, limit=100)  # Increased limit to get more results

    finalResults = []
    for result in tqdm(results['patentFileWrapperDataBag'], desc='Processing USPTO results'):
        application_number = result.get('applicationNumberText')
        tempResult = isolateDataFromUSPTOResults(result)

        pgpub_document_url = api.get_pgpub_document_url(str(application_number))
        grant_document_url = api.get_grant_document_url(str(application_number))
        doc_urls = []

        if((grant_document_url is not None) or (pgpub_document_url is not None)):
            if(grant_document_url is not None):
                doc_urls.append({
                    'source': 'uspto',
                    'url':grant_document_url
                })
                grant_content = readDocumentFromUrl(grant_document_url, headers={"X-API-KEY": getEnvKey('uspto')})
                grant_embedding = getPatentEmbedding(grant_content)
                grant_keywords = getKeywordsFromContent(grant_content)
                keywords.extend(grant_keywords)
                # if tempResult.get('document_embedding') is not None:
                #     tempResult['document_embedding'].append(grant_embedding)
                # else:
                #     tempResult['document_embedding'] = [grant_embedding]
            if(pgpub_document_url is not None):
                doc_urls.append({
                    'source': 'uspto',
                    'url': pgpub_document_url
                })
                pgpub_content = readDocumentFromUrl(pgpub_document_url, headers={"X-API-KEY": getEnvKey('uspto')})
                pgpub_embedding = getPatentEmbedding(pgpub_content)
                pgpub_keywords = getKeywordsFromContent(pgpub_content)
                keywords.extend(pgpub_keywords)
                # if tempResult.get('document_embedding') is not None:
                #     tempResult['document_embedding'].append(pgpub_embedding)
                # else:
                #     tempResult['document_embedding'] = [pgpub_embedding]
            tempResult['keywords'] = keywords
        tempResult['documents'] = doc_urls
        finalResults.append(tempResult)
    finalResults = getSimilarityScoresFromUSPTOResults(finalResults, load_to_database)
    if load_to_database:
        for result in finalResults:
            create_case(result)
    return finalResults

def getKeywordsFromPatent(documents:list[dict]):
    textContent = ""
    for document in documents:
        content = readDocumentFromUrl(url=document['url'], headers={"X-API-KEY": getEnvKey('uspto')})
        textContent = f"{textContent}\n\n{content}"
    keywords = getKeywordsFromContent(textContent)
    return keywords

def isolateDocumentFromUsptoById(document):
    if document is None:
        return None
    if 'downloadOptionBag' in document.keys():
        docOptionBag = document.get('downloadOptionBag')
        if type(docOptionBag) is list:
            docs_list = []
            for doc in docOptionBag:
                if 'downloadUrl' in doc.keys():
                    docs_list.append({
                        'source': 'uspto',
                        'url': doc.get('downloadUrl')
                    })
            return docs_list
    return None

def getEmbeddingOnline(text, api_key=None, model="text-embedding-3-small"):
    """
    Get the embedding of the text using OpenAI API.
    
    Args:
        text: The text to get embeddings for
        api_key: Optional OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
    
    Returns:
        List of floats representing the embedding vector
    """    
    # Initialize OpenAI client
    client = openai.OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
    
    response = client.embeddings.create(
        model=model,  # Using newer, cheaper model
        input=text
    )
    
    return response.data[0].embedding

def getEmbeddingOffline(text):
    """
    Generate an embedding vector for the given text using TF-IDF (Term Frequency-Inverse Document Frequency).
    This function uses scikit-learn's TfidfVectorizer to transform the input text into a TF-IDF feature vector.

    Args:
        text (str): The input text to be embedded.

    Returns:
        numpy.ndarray: The TF-IDF embedding vector for the input text.
    """
    

    vectorizer = TfidfVectorizer()
    # Since TF-IDF works at the document level, we treat the single input as a one-element corpus
    tfidf_matrix = vectorizer.fit_transform([text])
    embedding = tfidf_matrix.toarray()[0]
    return embedding

def getSimilarityScore(embedding1, embedding2):
    """
    Calculate the similarity score between two embeddings using cosine similarity.
    Args:
        embedding1: The first embedding vector
        embedding2: The second embedding vector
    Returns:
        float: The similarity score between the two embeddings
    """
    try:
        # Ensure both embeddings are 1D and have the same length before computing similarity
        if not hasattr(embedding1, "__len__") or not hasattr(embedding2, "__len__"):
            raise ValueError("Both embeddings must be sequences or arrays")
        if len(embedding1) != len(embedding2):
            raise ValueError(f"Embedding size mismatch: {len(embedding1)} vs {len(embedding2)}")
        # Check for NaN values or type issues
        if not isinstance(embedding1, (list, tuple, np.ndarray)) or not isinstance(embedding2, (list, tuple, np.ndarray)):
            raise TypeError("Both embeddings must be list, tuple, or numpy.ndarray")
        arr1 = np.asarray(embedding1)
        arr2 = np.asarray(embedding2)
        if np.isnan(arr1).any() or np.isnan(arr2).any():
            return -1
        score = np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
        if score < 0:
            score = abs(score)
        return score
    except Exception:
        return -1

def getBulkSimilarityScore(reference_embedding, embeddings_list):
    """
    Calculate similarity scores between a reference embedding and a list of embeddings.

    Args:
        reference_embedding: The embedding vector to compare others against.
        embeddings_list: List of embedding vectors to compare with the reference.

    Returns:
        List of float similarity scores.
    """
    scores = []
    # Check for invalid reference embedding: empty or contains NaN
    invalid_reference = False
    try:
        if reference_embedding is None:
            invalid_reference = True
        elif isinstance(reference_embedding, (list, tuple, np.ndarray)):
            ref_arr = np.asarray(reference_embedding)
            if ref_arr.size == 0 or np.isnan(ref_arr).any():
                invalid_reference = True
        else:
            invalid_reference = True

        if invalid_reference:
            return [-1 for _ in embeddings_list]
        for emb in embeddings_list:
            score = getSimilarityScore(reference_embedding, emb)
            scores.append(score)
    except Exception as e:
        print(f'Error in getBulkSimilarityScore: {str(e)}')
    return scores

def getEmbeddingsFromDocuments(documents):
    """
    Get the embeddings from the documents using the OpenAI API.
    Args:
        documents: List of document paths
    Returns:
        List of embeddings
    """
    embeddings = []
    for document in documents:
        documentText = readDocumentFromUrl(document)
        if documentText:
            documentEmbedding = getPatentEmbedding(documentText)
            embeddings.extend(documentEmbedding)
    return embeddings

def getPatentEmbedding(text, api_key=None):
    """
    Get the embedding of the text using OpenAI API.
    Args:
        text: The text to get embeddings for
        api_key: Optional OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
    Returns:
        List of floats representing the embedding vector
    """
    embedding = None
    if (text is None) or (text == ''):
        return None
    try:
        if api_key is not None:
            embedding = getEmbeddingOnline(text, api_key)
        else:
            embedding = getEmbeddingOffline(text)
    except Exception:
        if api_key is not None:
            embedding = getEmbeddingOnline(text, api_key)
        else:
            embedding = getEmbeddingOffline(text)
    return embedding

def generateReports(case_id):
    """
    Generate reports for a specific case
    Args:
        case_id: The ID of the case to generate reports for
    Returns:
        fullReport: The full report for the case
        summaryReport: The summary report for the case
    """
    case_data = get_case_by_id(case_id)
    references = case_data.get('references', [])
    documentTexts = []
    referenceText = ""

    # Get the text from related cases and all case related documents before generating reports
    if (references is not None) and (len(references) > 0):
        for ref in references:
            # Get the text from related cases
            document_text = readDocumentFromUrl(ref['url'])
            if document_text is not None:
                documentTexts.append(document_text, headers={"X-API-KEY": getEnvKey('uspto')})
            # Get the text from all case related documents
            case_document = case_data.get('documents', [])
            if (case_document is not None) and (len(case_document) > 0):
                for doc in case_document:
                    document_text = readDocumentFromUrl(doc['url'], headers={"X-API-KEY": getEnvKey('uspto')})
                    referenceText = f"{referenceText}\n\n{document_text}"

        fullReport = getCompleteReport(referenceText, documentTexts)
        summaryReport = getReportSummary(fullReport)
        case_data['report'] = fullReport
        case_data['summary'] = summaryReport
        update_case(case_id, case_data)
        return fullReport, summaryReport
    return None, None

def populateDummyData(case_id, user_id):
    title = 'HETEROJUNCTION BIPOLAR TRANSISTOR'
    dummy_report, dummy_summary = getDummyReportWithSummary(title)
    dummy_case = {
        '_id': f"dummy_{case_id}",
        'title': title,
        'status': 'Patented Case',
        'description': 'Patent Expired Due to NonPayment of Maintenance Fees Under 37 CFR 1.362',
        'currentStatusCode': 150,
        'currentStatusDate': '2016-05-18',
        'attorneys': [{
            'name': 'DANIEL D O\'BRIEN',
            'registrationNumber': '65545',
            'contact': '206-622-4900'
        }],    # Name, Registration Number, Contact
        'inventors': ['Pascal Chevalier'],    # List of names
        'mailingAddresses': [{
            "nameLineOneText": "Seed IP Law Group LLP/ST (EP ORIGINATING)",
            "nameLineTwoText": "Attn- IP Docket",
            'addressLineText': '701 FIFTH AVENUE, SUITE 5400, Suite 501',
            "geographicRegionName": "WASHINGTON",
            "geographicRegionCode": "WA",
            "postalCode": "98104-7092",
            "cityName": "SEATTLE",
            "countryCode": "US",
            "countryName": "USA",
            "postalAddressCategory": "commercial"
        }],  # cityName, geographicRegionName, geographicRegionCode, countryCode, postalCode, addressLineText
        'created_by': user_id,
        'created_date': datetime.datetime.utcnow().isoformat(),
        'filing_date': '2012-12-19',
        'documents': [{
            'source': 'uspto',
            'url': 'https://bulkdata.uspto.gov/data/patent/application/redbook/fulltext/2024/ipa240104.zip'
        }],
        'references': [{
            'url': 'https://bulkdata.uspto.gov/data/patent/application/redbook/fulltext/2024/ipa240104.zip',
            'title': 'ipa240801.zip',
            'granted_date': '2024-08-09:11:30:00',
            'similarity_rate': 95
        }],  # list of dictionaries with url, title, granted_date, similarity_rate,
        'report': dummy_report,
        'summary': dummy_summary,
    }
    print('Dummy Case: ', dummy_case)
    create_case(dummy_case)
    return dummy_case
import os
import json
import PyPDF2
import openai
import numpy as np
from dotenv import load_dotenv
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
    
    # Load environment variables
    load_dotenv()
    
    # Get API key from environment
    api_key = os.getenv('USPTO_API_KEY')
    
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
    from sklearn.feature_extraction.text import TfidfVectorizer
    import requests

    def fetch_text_from_url(url):
        # If URL is a http/https path, fetch and (if PDF, extract text)
        # If it's a local file path, open and read contents
        if url.startswith("http"):
            try:
                response = requests.get(url)
                response.raise_for_status()
                # Basic guess: PDF if endswith .pdf, else treat as text
                if url.lower().endswith('.pdf'):
                    import io
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
                    return readPdf(url)
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

def isolateDataFromUSPTOResults(result):
    """
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
    finalResult = {
        'applicationNumber': None,
        'title': None,
        'currentStatus': None,
        'currentStatusCode': None,
        'currentStatusDate': None,
        'attorneys': [],    # Name, Registration Number, Contact
        'inventors': [],    # List of names
        'mailingAddresses': [],  # cityName, geographicRegionName, geographicRegionCode, countryCode, postalCode, nameLineText
        'filingDate': None
    }
    return finalResult

def getKeywordDocumentsUSPTO(keywords:list[str]):
    """
    Get all documents/patents from the USPTO API related to the given keywords.

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
    print(json.dumps(results['patentFileWrapperDataBag'][0]['eventDataBag'], indent=4))
    finalResults = []
    for result in results['patentFileWrapperDataBag']:
        tempResult = isolateDataFromUSPTOResults(result)
        print('tempResult: ', json.dumps(tempResult, indent=4))
        finalResults.append(tempResult)
    
    return results

def readPdf(pdf_path):
    """
    Read a PDF file and return the text content.
    """
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return ""

def getEmbeddingOnline(text, api_key=None):
    """
    Get the embedding of the text using OpenAI API.
    
    Args:
        text: The text to get embeddings for
        api_key: Optional OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
    
    Returns:
        List of floats representing the embedding vector
    """
    import os
    
    # Initialize OpenAI client
    client = openai.OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
    
    response = client.embeddings.create(
        model="text-embedding-3-small",  # Using newer, cheaper model
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
        documentText = readPdf(document)
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
    try:
        embedding = getEmbeddingOnline(text, api_key)
    except Exception:
        embedding = getEmbeddingOffline(text)
    return embedding
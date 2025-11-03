import PyPDF2
import openai
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

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
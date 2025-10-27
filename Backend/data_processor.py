import PyPDF2
import openai
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

def readPdf(pdf_path):
    """
    Read a PDF file and return the text content.
    """
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
        return text

def getEmbedding(text, api_key=None):
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
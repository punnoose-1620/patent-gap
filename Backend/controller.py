import os
import uuid
from data_processor import *
from models.alerts import *
from data_processor import *
from models.cases import *

"""
Controller functions for handling business logic
"""

# Other Functions
def get_case_related_patents(case_id):
    """
    Get patents related to a specific case
    
    Args:
        case_id (str): Case identifier
    
    Returns:
        list: List of related patents
    """
    # TODO: Implement actual database query
    # Mock data for now
    caseData = get_case_by_id(case_id)
    allData = get_all_cases()
    related_patents = []
    for patent in allData:
        if(patent['_id'] != case_id):
            matches = 0
            totals = len(caseData['keywords'])
            for keyword in caseData['keywords']:
                if(keyword in patent['keywords']):
                    matches += 1
            if(matches / totals > 0):
                patent['similarity_rate'] = matches * 100 / totals
                related_patents.append(patent)
    return related_patents

def create_patent(patent_data):
    """
    Create a new patent
    
    Args:
        patent_data (dict): Patent information
    
    Returns:
        dict: Result containing success status and patent_id if successful
    """
    patent_id = f"local_{str(uuid.uuid4())[:8]}"
    print(f'Patent ID: {patent_id}')
    patent_data['_id'] = patent_id
    print(f'Patent data with ID: {patent_data}')
    # Change the key 'files' to 'references' if it exists in patent_data
    if 'files' in patent_data:
        patent_data['references'] = patent_data.pop('files')
    print(f'Patent data: ', json.dumps(patent_data, indent=4))

    return {
        'success': True,
        'message': 'Patent created successfully',
        'patent_id': patent_id,
        'patent': patent_data
    }

def process_new_patent(patent_id):
    """
    Process a new patent by extracting embeddings from its documents, comparing them
    with existing cases for similarity, and creating an alert if similar cases are found.
    
    The function reads all PDF documents associated with the patent, generates embeddings
    for them, and compares these embeddings with embeddings from all other cases using
    a similarity threshold of 0.8. Cases with similarity scores above the threshold are
    flagged, and an alert is created containing the users who created those similar cases.
    
    Args:
        patent_id (str): Patent identifier to process
    
    Returns:
        dict: Result containing success status, message, and alert_id if successful
    """
    # Find the case in cases with the given patent_id and get its 'documents' list
    threshold = 0.8         # Threshold for similarity score. Score will always be between 0 and 1.
    patentIds = []          # Reference for patent id: embeddings based on index
    alert_cases = []        # Reference for case ids that have been flagged as similar (beyond threshold) for this case
    patentDocuments = []    # Reference documents for this patent
    patentEmbeddings = []   # Embeddings from all documents for this patent
    other_embeddings = []   # Embeddings for all other cases
    # Get the case and its documents
    patentDocuments = get_documents_from_case(patent_id)
    # Read the documents and get the embeddings
    if len(patentDocuments) > 0:
        for document in patentDocuments:
            documentText = readPdf(document)
            documentEmbedding = getPatentEmbedding(documentText)
            patentEmbeddings.extend(documentEmbedding)
    # Get the similarity scores
    # Get the 'embeddings' for every entry in cases *excluding* the current case
    for case in get_all_cases_except_one(patent_id):
        patentIds.append(case.get('_id'))
        embeddings = case.get('embeddings', [])
        if embeddings:
            other_embeddings.append(embeddings)
    similarity_scores = getBulkSimilarityScore(patentEmbeddings, other_embeddings)
    # Flag cases that have a similarity score greater than the threshold
    for i in range(len(similarity_scores)):
        if similarity_scores[i] > threshold:
            alert_cases.append(patentIds[i])
    # Add the users list for this alert. Users are the ones who have created the cases that have been flagged as similar.
    alert_users = []
    for c_id in alert_cases:
        alert_users.append(get_case_creator(c_id))
    # Add this new alert to the alerts logs
    newId = add_to_alerts(triggered_by='case_001', triggered_at='2025-01-01', alert_users=alert_users)
    return {
        'success': True,
        'message': 'Alert created successfully',
        'alert_id': newId
    }

def getReferenceCase(case_id, user_id):
    """
    """
    refCase = get_case_by_id(case_id)
    # TODO: Get Embeddings for reference case
    my_cases = get_case_related_to_user(user_id)
    for case in my_cases:
        # TODO: Get Embeddings for each case and check similarity with the reference case
        print(case)
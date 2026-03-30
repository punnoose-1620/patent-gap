import re
from database import *
from models.documents import getDocumentById
from difflib import SequenceMatcher
from env_controller import getCaseDatabaseName

def string_fuzzy_similarity(s1, s2):
    """
    Perform a fuzzy comparison between two strings and return a similarity score between 0 and 1.
    Normalizes whitespace and performs a lower-case comparison using the SequenceMatcher ratio.
    """  

    if not isinstance(s1, str) or not isinstance(s2, str):
        return 0.0

    def normalize_string(s):
        return re.sub(r"\s+", " ", s.strip().lower())

    s1_norm = normalize_string(s1)
    s2_norm = normalize_string(s2)
    if not s1_norm and not s2_norm:
        return 1.0
    if not s1_norm or not s2_norm:
        return 0.0

    matcher = SequenceMatcher(None, s1_norm, s2_norm)
    return round(matcher.ratio(), 1)

def find_document_metadata(case_data):
    documents = case_data.get('documents', [])
    for entry in documents:
        if entry.get('source', '') == 'local':
            url = entry.get('url', '')
            document_id = url.split('/')[-1].split('.')[0]
            document = getDocumentById(document_id)
            if document.get('success', False):
                entry['title'] = document['document'].get('file_name', '')
                entry['size'] = document['document'].get('file_size', '')
                entry['type'] = document['document'].get('file_type', '')
                entry['created_at'] = document['document'].get('created_at', '')
                entry['created_by'] = document['document'].get('created_by', '')
    case_data['documents'] = documents
    return case_data

def get_all_cases():
    all_cases = getAllData(connect_to_database(), getCaseDatabaseName())
    for case in all_cases:
        case = find_document_metadata(case)
    return all_cases

def get_open_cases():
    """
    Get all open cases available for assignment
    
    Returns:
        list: List of open cases
    """
    open_cases = []
    for case in getAllData(connect_to_database(), getCaseDatabaseName()):
        if case['status'] != 'Completed':
            case = find_document_metadata(case)
            open_cases.append(case)
    return open_cases

def create_case(case_data):
    """
    Create a new case
    
    Args:
        case_data (dict): Case information
    
    Returns:
        dict: Result containing success status and case_id if successful
    """
    if '_id' not in case_data:
        return {
            'success': False,
            'message': 'Case ID is required'
        }
    addedId = addDataById(connect_to_database(), getCaseDatabaseName(), case_data)
    if addedId is not None:
        case_data['_id'] = addedId
        print(f'LOG: Case created successfully: {case_data["_id"]}')
        return {
            'success': True,
            'message': 'Case created successfully',
            'case_id': case_data['_id']
        }
    return {
        'success': False,
        'message': 'Failed to create case'
    }

def update_infringements(case_id, fresh_infringements):
    """
    Update the infringements list for a specific case.
    Meant to append infringements from each source without overall replacement
    """
    updated = updateListByIdAndKey(connect_to_database(), getCaseDatabaseName(), fresh_infringements, case_id, 'infringements')
    if updated:
        return {
            'success': True,
            'message': 'Infringements updated successfully'
        }
    return {
        'success': False,
        'message': 'Failed to update infringements'
    }

def update_case(case_id, update_data):
    """
    Update an existing case
    
    Args:
        case_id (str): Case identifier
        update_data (dict): Updated case information
    
    Returns:
        dict: Result containing success status
    """
    updated = updateDataById(connect_to_database(), getCaseDatabaseName(), update_data, case_id)
    if updated:
        return {
            'success': True,
            'message': 'Case updated successfully'
        }
    return {
        'success': False,
        'message': 'Case not found'
    }

def delete_case(case_id):
    """
    Delete a case
    
    Args:
        case_id (str): Case identifier
    
    Returns:
        dict: Result containing success status
    """
    deleted_id = deleteDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    if deleted_id is not None:
        return {
            'success': True,
            'message': 'Case deleted successfully'
        }
    return {
        'success': False,
        'message': 'Case not found'
    }

def get_case_by_id(case_id, show_password=False):
    """
    Get detailed information about a specific case
    
    Args:
        case_id (str): Case identifier
    
    Returns:
        dict: Case details or None if not found
    """
    all_cases = getAllData(connect_to_database(), getCaseDatabaseName())
    for case in all_cases:
        if (case.get('_id') == case_id) or (case.get('id') == case_id) or (case.get('case_id') == case_id):
            case = find_document_metadata(case)
            return case
    return None
    case = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    if case is not None:
        case = find_document_metadata(case)
        return case
    return None

def get_case_related_to_user(user_id):
    """
    Get cases related to a specific user (assigned to, accepted by, created by)
    
    Args:
        user_id (str): User's unique identifier
    
    Returns:
        list: List of user's cases
    """
    # TODO: Implement actual database query
    user_cases = []
    for case in getAllData(connect_to_database(), getCaseDatabaseName()):
        keys = case.keys()
        if ('assigned_to' in keys):
            if (case['assigned_to'] == user_id):
                case = find_document_metadata(case)
                user_cases.append(case)
                continue
        if ('accepted_by' in keys):
            if (case['accepted_by'] == user_id):
                case = find_document_metadata(case)
                user_cases.append(case)
                continue
        if ('created_by' in keys):
            if (case['created_by'] == user_id):
                case = find_document_metadata(case)
                user_cases.append(case)
                continue
    return user_cases

def get_documents_from_case(case_id):
    """
    Retrieve the list of documents associated with a specific case, given its case_id.

    Args:
        case_id (str): The unique identifier of the case.

    Returns:
        list: The 'documents' list from the matched case, or an empty list if the case is not found or has no documents.
    """
    case = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    patentDocuments = case.get('documents', [])
    return patentDocuments

def get_case_embedding(case_id):
    """
    Retrieve the embedding of a specific case, given its case_id.
    """
    case = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    if case is not None:
        return case.get('document_embedding')
    return {}

def get_all_cases_except_one(case_id):
    """
    Retrieve all cases except the one with the given case_id.

    Args:
        case_id (str): The unique identifier of the case to exclude.

    Returns:
        list: A list of all case dictionaries except the one matching the given case_id.
    """
    all_cases = []
    for case in getAllData(connect_to_database(), getCaseDatabaseName()):
        if case.get('_id') != case_id:
            all_cases.append(case)
    return all_cases

def get_case_creator(case_id):
    """
    Retrieve the creator of a specific case, given its case_id.

    Args:
        case_id (str): The unique identifier of the case.

    Returns:
        str: The 'created_by' value from the matched case, or None if the case is not found.
    """
    case = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    return case.get('created_by')

def get_infringement_chart(case_id):
    caseData = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    claims = caseData.get('claims', [])
    infringements = caseData.get('infringements', [])
    print('TEST 1: Claims')
    # If Claims and Infringements are not available, return None
    if (len(claims) == 0) or (len(infringements) == 0):
        return None
    # Let's remove the non-claims part of the claims list, like headings and such
    for claim in claims:
        if 'claim' not in claim:
            claims.remove(claim)
    print('TEST 2: Claims')
    # Now let's create a map of claims to their infringements
    returnVals = {}
    for infringement in infringements:
        entryId = infringement.get('entry_id', '')
        similarClaims = infringement.get('similar_claims', [])
        print('TEST 3: Similar Claims')
        for similarClaim in similarClaims:
            infringing_claim = similarClaim.get('claim', '')
            similarityScore = similarClaim.get('similarity_score', 0)
            found = False
            for c in claims:
                c = str(c).split('. ')[1].strip()
                print('\nTEST 4: Claim Comparison: \n', c, '\n', infringing_claim, '\n', c==infringing_claim, '\n', string_fuzzy_similarity(c, infringing_claim), '\n', similarityScore)
                if c==infringing_claim:
                    found = True
                if string_fuzzy_similarity(c, infringing_claim) >= (similarityScore-0.1):
                    found = True
            if not found:
                continue
            print('TEST 5: Claim')
            claimIndex = claims.index(claim)
            returnIndexKeys = returnVals.keys()
            if claimIndex not in returnIndexKeys:
                returnVals[claimIndex] = []
            returnVals[claimIndex].append({
                'entry_id': entryId,
                'similarity_score': similarityScore
            })
    # If Map is Empty, return None
    if returnVals=={}:
        return None
    return returnVals
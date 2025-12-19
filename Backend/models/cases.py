from database import *
from env_controller import getCaseDatabaseName
mock_cases = []

def get_all_cases():
    return getAllData(connect_to_database(), getCaseDatabaseName())

def get_open_cases():
    """
    Get all open cases available for assignment
    
    Returns:
        list: List of open cases
    """
    open_cases = []
    for case in getAllData(connect_to_database(), getCaseDatabaseName()):
        if case['status'] != 'Completed':
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

def update_case(case_id, update_data):
    """
    Update an existing case
    
    Args:
        case_id (str): Case identifier
        update_data (dict): Updated case information
    
    Returns:
        dict: Result containing success status
    """
    case = get_case_by_id(case_id, show_password=True)
    case.update(update_data)
    if case:
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
    for case in mock_cases:
        if case['_id'] == case_id:
            mock_cases.remove(case)
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
    return getDataById(connect_to_database(), getCaseDatabaseName(), case_id)

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
                user_cases.append(case)
                continue
        if ('accepted_by' in keys):
            if (case['accepted_by'] == user_id):
                user_cases.append(case)
                continue
        if ('created_by' in keys):
            if (case['created_by'] == user_id):
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
    # for case in mock_cases:
    #     if case.get('_id') == case_id:
    #         patentDocuments = case.get('documents', [])
    #         break
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
    # for case in mock_cases:
    #     if case.get('_id') == case_id:
    #         return case.get('created_by')
    # return 'Unknown'
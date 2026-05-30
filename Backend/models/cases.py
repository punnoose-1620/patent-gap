import re
from database import *
from models.documents import getDocumentById
from difflib import SequenceMatcher
from env_controller import getCaseDatabaseName
from scorer import score_infringement_matrix_entry

CLAIM_SIMILARITY_THRESHOLD = 0.1

def caseAlreadyExists(case_id:str, user_id: str):
    db = connect_to_database()
    db_name = getCaseDatabaseName()

    if '_' in case_id:
        case_id = case_id.split('_')[-1]

    if getDataById(db, db_name, case_id) is not None:
        return True

    sources = ['uspto', 'googlepatents', 'freepatentsonline', 'local']
    for source in sources:
        checker_id1 = f"{source}_{user_id}_{case_id}"
        checker_id2 = f"{source}_{case_id}"

        case1 = getDataById(db, db_name, checker_id1)
        case2 = getDataById(db, db_name, checker_id2)
        if (case1 is not None) or (case2 is not None):
            return True
    return False

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

def get_all_cases(page=1, paginated=False):
    if not paginated:
        all_cases = getAllData(connect_to_database(), getCaseDatabaseName())
        for case in all_cases:
            case = find_document_metadata(case)
        return all_cases
    paged = paginateDataByQuery(connect_to_database(), getCaseDatabaseName(), page=page)
    all_cases = paged.get('items', [])
    for case in all_cases:
        case = find_document_metadata(case)
    paged['items'] = all_cases
    return paged

def get_open_cases(page=1, paginated=False):
    """
    Get all open cases available for assignment
    
    Returns:
        list: List of open cases
    """
    if not paginated:
        open_cases = []
        for case in getAllData(connect_to_database(), getCaseDatabaseName()):
            if case['status'] != 'Completed':
                case = find_document_metadata(case)
                open_cases.append(case)
        return open_cases

    paged = paginateDataByQuery(
        connect_to_database(),
        getCaseDatabaseName(),
        query={'status': {'$ne': 'Completed'}},
        page=page
    )
    open_cases = paged.get('items', [])
    for case in open_cases:
        case = find_document_metadata(case)
    paged['items'] = open_cases
    return paged

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
        if 'DocumentCreationError' in case_data['_id']:
            return {
                'success': False,
                'message': 'Document creation error'
            }
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

def update_case_documents(case_id, update_data):
    """
    Update the documents list for a specific case.
    """
    updated = updateListByIdAndKey(connect_to_database(), getCaseDatabaseName(), update_data, case_id, 'documents')
    if updated:
        return {
            'success': True,
            'message': 'Case documents updated successfully'
        }
    return {
        'success': False,
        'message': 'Failed to update case documents'
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

def get_case_related_to_user(user_id, page=1, paginated=False):
    """
    Get cases related to a specific user (assigned to, accepted by, created by)
    
    Args:
        user_id (str): User's unique identifier
    
    Returns:
        list: List of user's cases
    """
    if not paginated:
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

    paged = paginateDataByQuery(
        connect_to_database(),
        getCaseDatabaseName(),
        query={
            '$or': [
                {'assigned_to': user_id},
                {'accepted_by': user_id},
                {'created_by': user_id}
            ]
        },
        page=page
    )
    user_cases = paged.get('items', [])
    for case in user_cases:
        case = find_document_metadata(case)
    paged['items'] = user_cases
    return paged

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
    """
    Build chart-ready infringement rows for a case.

    Returns a tuple ``(chart_data, error_code)``:

    - ``(rows, None)`` on success with a non-empty list.
    - ``([], 'NO_MATCHES_ABOVE_THRESHOLD')`` when claims and infringement claims
      were both present and scored, but no pair met the similarity threshold.
      Any newly computed scored rows are still persisted to the case document.
    - ``(None, 'CASE_NOT_FOUND')`` when no case exists for ``case_id``.
    - ``(None, 'NO_PARENT_CLAIMS')`` when the case has no usable parent claims.
    - ``(None, 'NO_INFRINGEMENTS')`` when the case has no infringements saved.
    - ``(None, 'INFRINGEMENT_CLAIMS_MISSING')`` when infringements exist but
      none of them carries any claims to compare against.
    """
    caseData = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    if caseData is None:
        return None, 'CASE_NOT_FOUND'

    claims = [claim for claim in caseData.get('claims', []) if isinstance(claim, str) and claim.strip() != '']
    if len(claims) == 0:
        return None, 'NO_PARENT_CLAIMS'

    infringements = caseData.get('infringements', [])
    if len(infringements) == 0:
        return None, 'NO_INFRINGEMENTS'

    chart_data = []
    has_updates = False
    entries_with_claims = 0

    for infringement_entry in infringements:
        if not isinstance(infringement_entry, dict):
            continue

        inf_claims = [
            c.strip()
            for c in infringement_entry.get('claims', [])
            if isinstance(c, str) and c.strip() != ''
        ]
        existing = infringement_entry.get('infringements')

        if not inf_claims and isinstance(existing, dict):
            legacy_claim = existing.get('claim')
            if isinstance(legacy_claim, str) and legacy_claim.strip() != '':
                inf_claims = [legacy_claim.strip()]

        if not inf_claims:
            continue

        entries_with_claims += 1

        if isinstance(existing, dict) and not infringement_entry.get('gemini_infringement'):
            infringement_entry['gemini_infringement'] = dict(existing)

        before = existing
        stored_rows, entry_chart_rows = score_infringement_matrix_entry(
            claims, inf_claims, existing, threshold=CLAIM_SIMILARITY_THRESHOLD
        )
        if stored_rows is None:
            continue

        infringement_entry['infringements'] = stored_rows
        chart_data.extend(entry_chart_rows)

        if before != stored_rows:
            has_updates = True

    if entries_with_claims == 0:
        return None, 'INFRINGEMENT_CLAIMS_MISSING'

    if has_updates:
        update_case(case_id, {'infringements': infringements})

    if len(chart_data) == 0:
        return [], 'NO_MATCHES_ABOVE_THRESHOLD'

    return chart_data, None
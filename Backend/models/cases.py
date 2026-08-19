import copy
import re
from database import *
from datetime import datetime as dt
from models.documents import getDocumentById
from difflib import SequenceMatcher
from env_controller import getCaseDatabaseName
from scorer import score_infringement_matrix_entry
from infringement_score_filters import (
    CLAIM_SIMILARITY_THRESHOLD,
    apply_infringement_filters_to_case,
    filter_chart_rows,
    filter_infringement_entry,
    filter_infringements_list,
)

_FUZZY_DEDUP_THRESHOLD = 0.9
_CLAIM_TYPE_KEYS = (
    'independent_claim',
    'asserted_claim',
    'core_claim',
    'pivotal_claim',
)

def has_delete_permission(user_id: str, case_id: str):
    """
    Check if the user has delete permission for the case.
    Only Creator and Owner can delete the case.
    """
    case_data = get_case_by_id(case_id)
    if not case_data:
        return False
    created_by = case_data.get('created_by')
    assigned_editors = case_data.get('assigned_editors') or []
    owner = case_data.get('owner')
    return (user_id == created_by) or (user_id == owner)

def has_edit_permission(user_id: str, case_id: str):
    """
    Check if the user has edit permission for the case.
    Only Creator, Owner and Assigned Editors can edit the case.
    """
    case_data = get_case_by_id(case_id)
    if not case_data:
        return False
    created_by = case_data.get('created_by')
    assigned_editors = case_data.get('assigned_editors') or []
    owner = case_data.get('owner')
    return (user_id == created_by) or (user_id in assigned_editors) or (user_id == owner)

def construct_id_regex(patent_id: str):
    """
    The regex constructed here is used to search for a same patent id in the database added by other users.
    For example, if the patent id is 1234567890, the regex will be _1234567890$.
    This will search for all additions by all other users.
    Case ID in database is of the format source_userid_patentid.
    We only want exact patent id matches, so we use $ at the end of the regex.
    """
    patent_id = (patent_id or "").strip()
    return f'_{re.escape(patent_id)}$'

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

def _normalize_merge_text(value) -> str:
    if not isinstance(value, str):
        return ''
    return re.sub(r'\s+', ' ', value.strip().lower())

def _normalize_url_key(value) -> str:
    return _normalize_merge_text(value).rstrip('/')

def _fuzzy_dedupe_strings(values) -> list:
    """Union strings with case- and light spelling-insensitive dedup."""
    result = []
    for raw in values or []:
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text:
            continue
        if any(
            string_fuzzy_similarity(text, existing) >= _FUZZY_DEDUP_THRESHOLD
            for existing in result
        ):
            continue
        result.append(text)
    return result

def _exact_dedupe_strings(values, key_fn=None) -> list:
    result = []
    seen = set()
    key_fn = key_fn or _normalize_merge_text
    for raw in values or []:
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text:
            continue
        key = key_fn(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result

def _claim_entry_is_filled(claim_data) -> bool:
    if not isinstance(claim_data, dict):
        return False
    documented = (claim_data.get('documented_claim') or '').strip()
    market = (claim_data.get('market_language_claim') or '').strip()
    return bool(documented or market)

def _claim_quality_score(claims) -> tuple:
    """
    Higher is better. Prefers more filled claims, then category coverage,
    then independent / asserted / core / pivotal counts.
    """
    if isinstance(claims, list):
        filled = sum(1 for c in claims if isinstance(c, str) and c.strip())
        return (filled, 0, 0, 0, 0, 0)
    if not isinstance(claims, dict):
        return (0, 0, 0, 0, 0, 0)

    counts = {key: 0 for key in _CLAIM_TYPE_KEYS}
    total = 0
    for claim_data in claims.values():
        if not _claim_entry_is_filled(claim_data):
            continue
        total += 1
        claim_type = claim_data.get('claim_type')
        if claim_type in counts:
            counts[claim_type] += 1

    categories_filled = sum(1 for count in counts.values() if count > 0)
    return (
        total,
        categories_filled,
        counts['independent_claim'],
        counts['asserted_claim'],
        counts['core_claim'],
        counts['pivotal_claim'],
    )

def _pick_best_claims_case(cases: list) -> dict | None:
    best_case = None
    best_score = (-1,)
    for case in cases or []:
        if not isinstance(case, dict):
            continue
        score = _claim_quality_score(case.get('claims'))
        if score > best_score:
            best_score = score
            best_case = case
    return best_case

def _pick_primary_case(cases: list, claims_case: dict | None) -> dict:
    if claims_case is not None:
        return claims_case

    def richness(case):
        infringements = case.get('infringements') or []
        keywords = case.get('keywords') or []
        description = case.get('description') or ''
        return (
            len(infringements) if isinstance(infringements, list) else 0,
            len(keywords) if isinstance(keywords, list) else 0,
            len(str(description)),
        )

    return max(cases, key=richness)

def _merge_search_limitations(cases: list) -> dict:
    companies = []
    urls = []
    priority_sources = []
    other = {}

    for case in cases or []:
        limitations = case.get('search_limitations') or {}
        if not isinstance(limitations, dict):
            continue
        companies.extend(limitations.get('companies') or [])
        urls.extend(limitations.get('urls') or [])
        for source in limitations.get('priority_target_sources') or []:
            if isinstance(source, dict):
                priority_sources.append(source)
            elif isinstance(source, str) and source.strip():
                priority_sources.append({'url': source.strip()})
        for key, value in limitations.items():
            if key in ('companies', 'urls', 'priority_target_sources'):
                continue
            if key in other:
                continue
            if value in (None, '', [], {}):
                continue
            other[key] = copy.deepcopy(value)

    merged = dict(other)
    merged['companies'] = _fuzzy_dedupe_strings(companies)
    merged['urls'] = _exact_dedupe_strings(urls, key_fn=_normalize_url_key)

    seen_priority = set()
    unique_priority = []
    for source in priority_sources:
        url = _normalize_url_key(source.get('url') or '')
        title = _normalize_merge_text(source.get('title') or '')
        key = url or title
        if not key or key in seen_priority:
            continue
        seen_priority.add(key)
        unique_priority.append(source)
    if unique_priority:
        merged['priority_target_sources'] = unique_priority
    return merged

def _infringement_dedupe_key(entry) -> tuple | None:
    if not isinstance(entry, dict):
        return None

    product_id = str(entry.get('product_id') or '').strip().lower()
    product_url = _normalize_url_key(
        entry.get('product_url') or entry.get('url') or ''
    )
    if product_id or product_url:
        return ('product', product_id, product_url)

    patent_ref = (
        entry.get('entry_id')
        or entry.get('patent')
        or entry.get('case_id')
        or entry.get('patent_id')
    )
    if patent_ref:
        return ('patent', str(patent_ref).strip().lower())

    entry_id = str(entry.get('_id') or '').strip()
    if entry_id:
        return ('id', entry_id.lower())
    return None

def _merge_unique_dict_list(lists, key_fn) -> list:
    merged = []
    seen = set()
    for values in lists:
        for item in values or []:
            key = key_fn(item)
            if key is None:
                if item not in merged:
                    merged.append(copy.deepcopy(item))
                continue
            if key in seen:
                continue
            seen.add(key)
            merged.append(copy.deepcopy(item))
    return merged

def _case_source_prefix(case: dict) -> str:
    source = case.get('source')
    if isinstance(source, str) and source.strip():
        return source.strip()
    case_id = str(case.get('_id') or '')
    if '_' in case_id:
        return case_id.split('_', 1)[0]
    return 'googlepatents'

def get_similar_cases(patent_id: str, user_id: str):
    """
    Get all cases similar to the given patent id.
    Combine the infringements and related values from all into a single list.
    Replace creator id and assigned to id with the given user id.
    New case ID must be originalSource_newUserId_patentId.
    Remove the key for 'notes' from the case.
    Important: Multiple cases can be returned. Use all of them to combine into a
    single case with no duplicate values for any metadata entries or infringements
    or chart values.
    """
    patent_id = (patent_id or '').strip()
    user_id = (user_id or '').strip()
    if not patent_id or not user_id:
        return None

    regex_id = construct_id_regex(patent_id)
    cases = getDataContainingIdString(
        connect_to_database(), getCaseDatabaseName(), regex_id
    ) or []
    cases = [case for case in cases if isinstance(case, dict)]
    if not cases:
        return None

    claims_case = _pick_best_claims_case(cases)
    primary = _pick_primary_case(cases, claims_case)
    combined = copy.deepcopy(primary)

    source = _case_source_prefix(primary)
    combined['_id'] = f'{source}_{user_id}_{patent_id}'
    combined['created_by'] = user_id
    combined['assigned_to'] = user_id
    combined['source'] = source
    combined['last_updated'] = dt.now().isoformat()
    combined.pop('notes', None)

    combined['keywords'] = _fuzzy_dedupe_strings(
        [kw for case in cases for kw in (case.get('keywords') or [])]
    )
    combined['owners'] = _fuzzy_dedupe_strings(
        [owner for case in cases for owner in (case.get('owners') or [])]
    )
    combined['search_limitations'] = _merge_search_limitations(cases)
    combined['claims'] = copy.deepcopy(
        (claims_case or primary).get('claims')
    )

    combined['infringements'] = _merge_unique_dict_list(
        [case.get('infringements') for case in cases],
        _infringement_dedupe_key,
    )
    combined['documents'] = _merge_unique_dict_list(
        [case.get('documents') for case in cases],
        lambda doc: (
            ('url', _normalize_url_key((doc or {}).get('url') or ''))
            if isinstance(doc, dict) and (doc.get('url') or '').strip()
            else None
        ),
    )
    combined['document_urls'] = _exact_dedupe_strings(
        [url for case in cases for url in (case.get('document_urls') or [])],
        key_fn=_normalize_url_key,
    )
    combined['excluded_case_ids'] = _exact_dedupe_strings(
        [value for case in cases for value in (case.get('excluded_case_ids') or [])]
    )
    combined['excluded_case_titles'] = _fuzzy_dedupe_strings(
        [value for case in cases for value in (case.get('excluded_case_titles') or [])]
    )
    combined['inventors'] = _fuzzy_dedupe_strings(
        [value for case in cases for value in (case.get('inventors') or [])]
    )
    combined['attorneys'] = _fuzzy_dedupe_strings(
        [value for case in cases for value in (case.get('attorneys') or [])]
    )
    combined['current_assignee'] = _fuzzy_dedupe_strings(
        [value for case in cases for value in (case.get('current_assignee') or [])]
    )
    combined['other_ids'] = _exact_dedupe_strings(
        [value for case in cases for value in (case.get('other_ids') or [])]
    )

    for scalar_key in (
        'title',
        'description',
        'status',
        'country',
        'applicant',
        'filingDate',
        'currentStatusDate',
        'currentStatusCode',
    ):
        if combined.get(scalar_key) not in (None, '', [], {}):
            continue
        for case in cases:
            value = case.get(scalar_key)
            if value not in (None, '', [], {}):
                combined[scalar_key] = copy.deepcopy(value)
                break

    combined = find_document_metadata(combined)
    try:
        get_infringement_chart(case_data=combined, persist=False)
    except Exception as score_err:
        print(f'LOG: in-memory score refresh failed for {combined.get("_id")}: {score_err}')
    return apply_infringement_filters_to_case(combined)

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

def get_case_by_id(case_id, apply_infringement_filters: bool = True):
    case = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    if case is not None:
        case = find_document_metadata(case)
        if apply_infringement_filters:
            return apply_infringement_filters_to_case(case)
        else:
            return case
    return None

def get_all_cases(page=1, paginated=False):
    if not paginated:
        all_cases = getAllData(connect_to_database(), getCaseDatabaseName())
        for case in all_cases:
            case = find_document_metadata(case)
            case = apply_infringement_filters_to_case(case)
        return all_cases
    paged = paginateDataByQuery(connect_to_database(), getCaseDatabaseName(), page=page)
    all_cases = paged.get('items', [])
    for i, case in enumerate(all_cases):
        case = find_document_metadata(case)
        all_cases[i] = apply_infringement_filters_to_case(case)
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
                case = apply_infringement_filters_to_case(case)
                open_cases.append(case)
        return open_cases

    paged = paginateDataByQuery(
        connect_to_database(),
        getCaseDatabaseName(),
        query={'status': {'$ne': 'Completed'}},
        page=page
    )
    open_cases = paged.get('items', [])
    for i, case in enumerate(open_cases):
        case = find_document_metadata(case)
        open_cases[i] = apply_infringement_filters_to_case(case)
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
    fresh_infringements = filter_infringements_list(fresh_infringements or [])
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
            if not show_password:
                case.pop('password', None)
            return apply_infringement_filters_to_case(case)
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
                    user_cases.append(apply_infringement_filters_to_case(case))
                    continue
            if ('accepted_by' in keys):
                if (case['accepted_by'] == user_id):
                    case = find_document_metadata(case)
                    user_cases.append(apply_infringement_filters_to_case(case))
                    continue
            if ('created_by' in keys):
                if (case['created_by'] == user_id):
                    case = find_document_metadata(case)
                    user_cases.append(apply_infringement_filters_to_case(case))
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
    for i, case in enumerate(user_cases):
        case = find_document_metadata(case)
        user_cases[i] = apply_infringement_filters_to_case(case)
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

def update_infringement_analysis_flags(
    case_id:str, 
    category:str = "patent", 
    update_type:str = 'started',
    error_message:str = '',
    time_taken:str = ''
    ):
    case_data = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    if case_data is None:
        return False

    patent_time_taken = case_data.get('patent_analysis_time_taken', '')
    product_time_taken = case_data.get('product_analysis_time_taken', '')
    last_updated = dt.now()
    next_status = 'Started'
    update_data = {
        'last_updated': last_updated,
        'infringement_analysis_status': next_status
    }
    existing_status = case_data.get('infringement_analysis_status', '')
    if update_type.strip().lower() == 'completed':
        if patent_time_taken != '' and product_time_taken != '':
            next_status = 'Completed'
            update_data['last_infringement_analysis_date'] = dt.now()
        else:
            if category == 'patent':
                if time_taken != '':
                    update_data[f'{category}_analysis_time_taken'] = time_taken
                if 'product' in existing_status.strip().lower():
                    next_status = 'Completed'
                    update_data['last_infringement_analysis_date'] = dt.now()
                else:
                    next_status = 'Patent Sources Completed'
            elif category == 'product':
                if time_taken != '':
                    update_data[f'{category}_analysis_time_taken'] = time_taken
                if 'patent' in existing_status.strip().lower():
                    next_status = 'Completed'
                    update_data['last_infringement_analysis_date'] = dt.now()
                else:
                    next_status = 'Product Sources Completed'
    elif update_type.strip().lower() == 'error':
        next_status = 'Error'
        if error_message != '':
            next_status += f': {error_message}'
        if time_taken != '':
            update_data[f'{category}_analysis_time_taken'] = time_taken
    else:
        next_status = 'Started'
    update_data['infringement_analysis_status'] = next_status
    update_case(case_id, update_data)
    return True

def update_infringement_analysis_status(
    case_id:str,
    status:str = 'started',
    update_type:str = "patent",
    generic_bucket:str = None,
    asserted_bucket:str = None, 
    independent_bucket:str = None, 
    core_bucket:str = None, 
    pivotal_bucket:str = None,
    error_message:str = None,
    reset_flags:bool = False
    ):
    default_status = ""
    if status.strip().lower() == "completed":
        default_status = "Completed"
    elif status.strip().lower() == "error":
        default_status = "Error"
        if error_message is not None:
            default_status += f': {error_message}'
    else:
        default_status = "Started"
    
    generic_key = f'generic_claims_{update_type}_analysis'
    assert_key = f'asserted_claims_{update_type}_analysis'
    independent_key = f'independent_claims_{update_type}_analysis'
    core_key = f'core_claims_{update_type}_analysis'
    pivotal_key = f'pivotal_claims_{update_type}_analysis'

    status_key = f'{update_type}_status_flags'

    case_data = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    old_status_flags = case_data.get(status_key, {})
    if old_status_flags is None or old_status_flags == {} or reset_flags:
        old_status_flags = {
            generic_key: default_status,
            assert_key: default_status,
            independent_key: default_status,
            core_key: default_status,
            pivotal_key: default_status
        }

    if not reset_flags:
        if generic_bucket is not None:
            old_status_flags[generic_key] = generic_bucket
        if asserted_bucket is not None:
            old_status_flags[assert_key] = asserted_bucket
        if independent_bucket is not None:
            old_status_flags[independent_key] = independent_bucket
        if core_bucket is not None:
            old_status_flags[core_key] = core_bucket
        if pivotal_bucket is not None:
            old_status_flags[pivotal_key] = pivotal_bucket

    update_data_new = {
        'last_updated': dt.now()
    }
    update_data_new[status_key] = old_status_flags
    if status.strip().lower() == "started":
        update_data_new['infringement_analysis_status'] = "Started"
    update_case(case_id, update_data_new)
    return True

def _chart_error(error_code: str):
    return [], [], [], error_code


def get_infringement_chart(case_id=None, case_data=None, persist=True):
    """
    Build chart-ready infringement rows for a case.

    Returns ``(chart_data, patent_chart_data, product_chart_data, error_code)``:

    - Last element ``None`` on success with a non-empty chart.
    - ``([], [], [], 'NO_MATCHES_ABOVE_THRESHOLD')`` when scoring ran but no pair
      met the threshold (rows may still be persisted).
    - ``([], [], [], <ERROR_CODE>)`` for CASE_NOT_FOUND, NO_PARENT_CLAIMS, etc.

    Pass ``case_data`` to score an in-memory case (e.g. before insert).
    Set ``persist=False`` to mutate ``case_data['infringements']`` without writing to DB.
    """
    caseData = case_data
    if caseData is None:
        caseData = getDataById(connect_to_database(), getCaseDatabaseName(), case_id)
    if caseData is None:
        return _chart_error('CASE_NOT_FOUND')

    claims_original_list = caseData.get('claims', [])
    claims = []
    original_claims = []
    market_claims = []
    if isinstance(claims_original_list, list) and all(isinstance(claim, str) for claim in claims_original_list):
        for claim in claims_original_list:
            if claim is None:
                continue
            if claim.strip() != '':
                claims.append(claim.strip())
    elif isinstance(claims_original_list, dict):
        for index, claimData in claims_original_list.items():
            if not isinstance(claimData, dict):
                continue
            documented = (claimData.get('documented_claim') or '').strip()
            market = (claimData.get('market_language_claim') or '').strip()
            if documented:
                claims.append(documented)
                original_claims.append(documented)
            if market:
                market_claims.append(market)
    if not claims and not original_claims and not market_claims:
        return _chart_error('NO_PARENT_CLAIMS')

    infringements = caseData.get('infringements', [])
    if len(infringements) == 0:
        return _chart_error('NO_INFRINGEMENTS')

    chart_data = []
    patent_chart_data = []
    product_chart_data = []
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
            gemini_hint = infringement_entry.get('gemini_infringement')
            if isinstance(gemini_hint, dict):
                hint_claim = gemini_hint.get('claim')
                if isinstance(hint_claim, str) and hint_claim.strip():
                    inf_claims = [hint_claim.strip()]

        if not inf_claims:
            continue

        is_product = bool(infringement_entry.get('product_id'))
        if is_product:
            ref_claims = market_claims if market_claims else claims
        else:
            ref_claims = original_claims if original_claims else claims

        if not ref_claims:
            continue

        entries_with_claims += 1

        if isinstance(existing, dict) and not infringement_entry.get('gemini_infringement'):
            infringement_entry['gemini_infringement'] = dict(existing)

        before = existing
        stored_rows, entry_chart_rows = score_infringement_matrix_entry(
            ref_claims, inf_claims, existing, threshold=CLAIM_SIMILARITY_THRESHOLD
        )
        if stored_rows is None:
            continue

        infringement_entry['infringements'] = stored_rows
        chart_data.extend(entry_chart_rows)
        if is_product:
            product_chart_data.extend(entry_chart_rows)
        else:
            patent_chart_data.extend(entry_chart_rows)

        if before != stored_rows:
            has_updates = True

    if entries_with_claims == 0:
        return _chart_error('INFRINGEMENT_CLAIMS_MISSING')

    chart_data = filter_chart_rows(chart_data)
    patent_chart_data = filter_chart_rows(patent_chart_data)
    product_chart_data = filter_chart_rows(product_chart_data)

    for infringement_entry in infringements:
        if not isinstance(infringement_entry, dict):
            continue
        filtered_entry = filter_infringement_entry(infringement_entry)
        if filtered_entry != infringement_entry:
            infringement_entry.clear()
            infringement_entry.update(filtered_entry)
            has_updates = True

    if persist and has_updates and case_id:
        update_case(case_id, {'infringements': infringements})

    if len(chart_data) == 0:
        return [], [], [], 'NO_MATCHES_ABOVE_THRESHOLD'

    return chart_data, patent_chart_data, product_chart_data, None


def refresh_case_infringement_scores(case_id=None, case_data=None, persist=True):
    """
    Recompute embedding scores for all infringements on a case and optionally
    persist pairs above CLAIM_SIMILARITY_THRESHOLD. Also strips sub-threshold
    Gemini rows. Pass case_data with persist=False to score before DB insert.
    """
    return get_infringement_chart(case_id=case_id, case_data=case_data, persist=persist)
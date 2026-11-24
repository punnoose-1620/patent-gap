import copy
import re
from urllib.parse import urlparse
from database import *
from datetime import datetime as dt
from structures.documents import getDocumentsByCaseId
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
    local_entries = [e for e in documents if isinstance(e, dict) and e.get('source', '') == 'local']
    if not local_entries:
        case_data['documents'] = documents
        return case_data

    case_id = case_data.get('_id') or case_data.get('id') or case_data.get('case_id')
    docs_by_id = {}
    if case_id:
        fetched = getDocumentsByCaseId(case_id, exclude_fields=['file_content'])
        for doc in fetched.get('documents') or []:
            doc_id = str(doc.get('_id') or doc.get('id') or '')
            if doc_id:
                docs_by_id[doc_id] = doc

    for entry in local_entries:
        url = entry.get('url', '')
        document_id = url.split('/')[-1].split('.')[0]
        document = docs_by_id.get(document_id)
        if not document:
            continue
        entry['title'] = document.get('file_name', '')
        entry['size'] = document.get('file_size', '')
        entry['type'] = document.get('file_type', '')
        entry['created_at'] = document.get('created_at', '')
        entry['created_by'] = document.get('created_by', '')
    case_data['documents'] = documents
    return case_data

def get_case_by_id(
    case_id,
    apply_infringement_filters: bool = True,
    show_password: bool = False,
):
    """
    Fetch one case by id via Mongo ``getDataById`` (direct ``_id`` lookup).

    Falls back to ``id`` / ``case_id`` key lookups without loading the full
    collection. Pass ``show_password=True`` to keep a ``password`` field if present.
    """
    db = connect_to_database()
    coll = getCaseDatabaseName()
    case = getDataById(db, coll, case_id)
    if case is None and case_id:
        for key in ('id', 'case_id'):
            found = getDataByKeyValue(db, coll, key, case_id)
            if found:
                case = found[0] if isinstance(found, list) else found
                break
    if case is None:
        return None

    case = find_document_metadata(case)
    if not show_password:
        case.pop('password', None)
    if apply_infringement_filters:
        return apply_infringement_filters_to_case(case)
    return case

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

def _user_cases_query(user_id):
    return {
        '$or': [
            {'assigned_to': user_id},
            {'accepted_by': user_id},
            {'created_by': user_id},
        ]
    }

def get_cases_by_query(query, include_fields=None, exclude_fields=None):
    """
    Lean Mongo find for cases. Prefer this over getAllData for filtered loads.
    """
    return getDataByQuery(
        connect_to_database(),
        getCaseDatabaseName(),
        query or {},
        include_fields=include_fields,
        exclude_fields=exclude_fields,
    )

def get_unsorted_cases_for_user(user_id, include_fields=None):
    """
    Cases related to ``user_id`` with no folder membership
    (missing / null / empty ``folders``).
    """
    if not user_id:
        return []
    query = {
        '$and': [
            _user_cases_query(user_id),
            {
                '$or': [
                    {'folders': {'$exists': False}},
                    {'folders': None},
                    {'folders': {'$size': 0}},
                ]
            },
        ]
    }
    fields = include_fields if include_fields is not None else ['_id']
    return get_cases_by_query(query, include_fields=fields)

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

    patent_time_taken = case_data.get('patent_analysis_time_taken', '') or ''
    product_time_taken = case_data.get('product_analysis_time_taken', '') or ''
    last_updated = dt.now()
    next_status = 'Started'
    update_data = {
        'last_updated': last_updated,
        'infringement_analysis_status': next_status
    }
    if update_type.strip().lower() == 'completed':
        # Write this side's time, then decide overall status from both times:
        # - other side empty → Patent/Product Sources Completed
        # - both set → Completed
        if time_taken != '':
            update_data[f'{category}_analysis_time_taken'] = time_taken
        if category == 'patent':
            patent_time_taken = time_taken or patent_time_taken
            if not product_time_taken:
                next_status = 'Patent Sources Completed'
            else:
                next_status = 'Completed'
                update_data['last_infringement_analysis_date'] = dt.now()
        elif category == 'product':
            product_time_taken = time_taken or product_time_taken
            if not patent_time_taken:
                next_status = 'Product Sources Completed'
            else:
                next_status = 'Completed'
                update_data['last_infringement_analysis_date'] = dt.now()
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
    # Bucket flag updates must not touch overall infringement_analysis_status.
    # That field is owned by update_infringement_analysis_flags (patent/product
    # thread start + finalize). Default status='started' on every bucket call
    # previously wiped "Patent/Product Sources Completed" back to "Started",
    # so dual-thread runs never reached "Completed".
    update_case(case_id, update_data_new)
    return True

def _chart_error(error_code: str):
    return [], [], [], error_code


def _entry_has_scored_matrix_rows(entry) -> bool:
    nested = entry.get('infringements') if isinstance(entry, dict) else None
    return (
        isinstance(nested, list)
        and bool(nested)
        and isinstance(nested[0], dict)
        and 'calculated_similarity_score' in nested[0]
    )


def _can_serve_chart_from_stored_scores(infringements) -> bool:
    """
    New-structure cases already carry embedding matrix rows on each hit.
    Serve those instead of rebuilding (avoids TF-IDF/embed + update_case).

    Empty nested ``infringements`` (e.g. after score filtering) does not force a
    rebuild. Only legacy shapes do: a Gemini dict, or a non-empty list without
    ``calculated_similarity_score``.
    """
    saw_scored = False
    for entry in infringements or []:
        if not isinstance(entry, dict):
            continue
        nested = entry.get('infringements')
        if isinstance(nested, list) and nested:
            if isinstance(nested[0], dict) and 'calculated_similarity_score' in nested[0]:
                saw_scored = True
            else:
                return False
        elif isinstance(nested, dict):
            return False
    return saw_scored


def _chart_rows_from_stored_entry(entry) -> list:
    nested = entry.get('infringements') or []
    if not isinstance(nested, list):
        return []
    entry_id = (
        entry.get('product_id')
        or entry.get('case_id')
        or entry.get('entry_id')
        or entry.get('_id')
        or entry.get('product_name')
        or entry.get('title')
        or ''
    )
    rows = []
    for row in nested:
        if not isinstance(row, dict):
            continue
        if 'calculated_similarity_score' not in row:
            continue
        chart_row = dict(row)
        if entry_id and not chart_row.get('entry_id'):
            chart_row['entry_id'] = entry_id
        rows.append(chart_row)
    return rows


def _build_chart_from_stored_scores(infringements):
    chart_data = []
    patent_chart_data = []
    product_chart_data = []
    for entry in infringements or []:
        if not isinstance(entry, dict) or not _entry_has_scored_matrix_rows(entry):
            continue
        rows = _chart_rows_from_stored_entry(entry)
        if not rows:
            continue
        chart_data.extend(rows)
        if entry.get('product_id'):
            product_chart_data.extend(rows)
        else:
            patent_chart_data.extend(rows)

    chart_data = filter_chart_rows(chart_data)
    patent_chart_data = filter_chart_rows(patent_chart_data)
    product_chart_data = filter_chart_rows(product_chart_data)
    if not chart_data:
        return [], [], [], 'NO_MATCHES_ABOVE_THRESHOLD'
    return chart_data, patent_chart_data, product_chart_data, None


def get_infringement_chart(case_id=None, case_data=None, persist=True):
    """
    Build chart-ready infringement rows for a case.

    Returns ``(chart_data, patent_chart_data, product_chart_data, error_code)``:

    - Last element ``None`` on success with a non-empty chart.
    - ``([], [], [], 'NO_MATCHES_ABOVE_THRESHOLD')`` when scoring ran but no pair
      met the threshold (rows may still be persisted).
    - ``([], [], [], <ERROR_CODE>)`` for CASE_NOT_FOUND, NO_PARENT_CLAIMS, etc.

    When infringements already carry ``calculated_similarity_score`` matrix rows
    (new structure), returns those without rebuilding or persisting.

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
        def _claim_key_order(item):
            key = item[0]
            try:
                return (0, int(key))
            except (TypeError, ValueError):
                return (1, str(key))

        for _index, claimData in sorted(claims_original_list.items(), key=_claim_key_order):
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

    if _can_serve_chart_from_stored_scores(infringements):
        print(
            f"LOG: Serving infringement chart from stored scores "
            f"(skip rebuild) case_id={case_id or caseData.get('_id')}"
        )
        return _build_chart_from_stored_scores(infringements)

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
            ref_claims,
            inf_claims,
            existing,
            threshold=CLAIM_SIMILARITY_THRESHOLD,
            user_id=caseData.get('created_by') or caseData.get('owner'),
            case_id=case_id or caseData.get('_id'),
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


# ---------------------------------------------------------------------------
# First-fetch search_limitations seeding (companies + URLs)
# MCP exposes only add_limitations; validators below are private helpers.
# ---------------------------------------------------------------------------

_COMMERCIAL_LAYERS = frozenset(
    {
        "finished_device",
        "component_part",
        "medicine_consumable",
        "software_service",
        "method_only",
    }
)
_COMMERCIAL_LAYER_ALIASES = {
    "device": "finished_device",
    "finished device": "finished_device",
    "finished-device": "finished_device",
    "product": "finished_device",
    "component": "component_part",
    "part": "component_part",
    "component/part": "component_part",
    "medicine": "medicine_consumable",
    "drug": "medicine_consumable",
    "consumable": "medicine_consumable",
    "software": "software_service",
    "service": "software_service",
    "method": "method_only",
    "process": "method_only",
}
_CONFIDENCE_VALUES = frozenset({"high", "medium", "low"})
_URL_BUCKET_KEYS = ("home_page", "product_listings", "support_docs")
_LIMITATION_URL_TIMEOUT_S = 12
_LIMITATION_URL_MAX_PER_CALL = 12
_LIMITATION_URL_BODY_BYTES = 65536
_SENTENCE_SPLIT_RE = re.compile(r"[.!?\n\r]+")

# Marketplace / retailer hosts are never valid search-limitation focus URLs.
_MARKETPLACE_HOST_SUFFIXES = (
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.ca",
    "amazon.co.jp",
    "ebay.com",
    "ebay.co.uk",
    "ebay.de",
    "walmart.com",
    "bestbuy.com",
    "homedepot.com",
    "lowes.com",
    "alibaba.com",
    "aliexpress.com",
    "gsmarena.com",
    "newegg.com",
    "target.com",
)

_SOFT_404_MARKERS = (
    "page not found",
    "pages you visit may have changed",
    "does not exist",
    "no longer available",
    "has been removed",
    "error 404",
    "404 not found",
    "we can't find that page",
    "we couldn’t find that page",
    "this page isn't available",
    "this page isn’t available",
)

_ACCESS_DENIED_MARKERS = (
    "access denied",
    "permission denied",
    "request denied",
    "forbidden",
    "not authorized",
    "unauthorized",
    "unusual traffic",
    "automated queries",
    "are you a robot",
    "are you human",
    "i'm not a robot",
    "i’m not a robot",
    "captcha",
    "cf-browser-verification",
    "cf-challenge",
    "just a moment",
    "attention required",
    "enable javascript and cookies",
    "please enable cookies",
    "bot detection",
    "security check",
    "verify you are a human",
    "verify you're a human",
    "verify that you are human",
)


def _normalize_commercial_layer(value) -> tuple[str | None, str | None]:
    """
    Map agent commercial_layer to a fixed enum.
    Returns (layer, error). error is set when empty/unknown.
    """
    raw = str(value or "").strip().lower().replace("-", "_")
    if not raw or raw in ("none", "null", "n/a", "na"):
        return None, "commercial_layer is empty or null"
    compact = re.sub(r"[\s/]+", "_", raw)
    spaced = raw.replace("_", " ")
    if compact in _COMMERCIAL_LAYERS:
        return compact, None
    if spaced in _COMMERCIAL_LAYER_ALIASES:
        return _COMMERCIAL_LAYER_ALIASES[spaced], None
    if compact in _COMMERCIAL_LAYER_ALIASES:
        return _COMMERCIAL_LAYER_ALIASES[compact], None
    return None, (
        f"commercial_layer {value!r} is not one of: "
        + ", ".join(sorted(_COMMERCIAL_LAYERS))
    )


def _normalize_classification_text(value, *, field: str, min_len: int) -> tuple[str | None, str | None]:
    """Require a non-empty plain-text classification field."""
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text or text.lower() in ("none", "null", "n/a", "na"):
        return None, f"{field} is empty or null"
    if len(text) < min_len:
        return None, f"{field} is too short (need ≥{min_len} chars)"
    return text, None


def _commercial_classification_complete(limitations: dict | None) -> bool:
    """True when layer + sellable_unit + buyer + why_this_layer are all set."""
    if not isinstance(limitations, dict):
        return False
    layer, layer_err = _normalize_commercial_layer(limitations.get("commercial_layer"))
    if layer_err or not layer:
        return False
    for field, min_len in (
        ("sellable_unit", 3),
        ("buyer", 3),
        ("why_this_layer", 12),
    ):
        _, err = _normalize_classification_text(
            limitations.get(field), field=field, min_len=min_len
        )
        if err:
            return False
    return True


def _check_company_suggestion_entries(companies) -> tuple[list[str], list[str]]:
    """
    Validate suggestion company rows.
    Each entry needs non-empty name, reason, and confidence in high|medium|low.
    Returns (accepted_names, error_strings). Names only are persisted.
    """
    accepted: list[str] = []
    errors: list[str] = []
    if companies is None:
        return accepted, errors
    if not isinstance(companies, list):
        return accepted, ["companies must be a list"]

    for index, entry in enumerate(companies):
        prefix = f"companies[{index}]"
        if isinstance(entry, str):
            name = entry.strip()
            if not name:
                errors.append(f"{prefix}: name is empty")
                continue
            errors.append(
                f"{prefix}: expected object with name, reason, confidence "
                f"(got bare string {name!r})"
            )
            continue
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: expected object with name, reason, confidence")
            continue
        name = str(entry.get("name") or "").strip()
        reason = str(entry.get("reason") or "").strip()
        confidence = str(entry.get("confidence") or "").strip().lower()
        if not name:
            errors.append(f"{prefix}: name is empty")
            continue
        if not reason:
            errors.append(f"{prefix} ({name!r}): reason is empty")
            continue
        if confidence not in _CONFIDENCE_VALUES:
            errors.append(
                f"{prefix} ({name!r}): confidence must be high|medium|low "
                f"(got {entry.get('confidence')!r})"
            )
            continue
        accepted.append(name)
    return accepted, errors


def _limitation_url_host(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").strip().lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _limitation_url_is_marketplace(url: str) -> bool:
    host = _limitation_url_host(url)
    if not host:
        return False
    for suffix in _MARKETPLACE_HOST_SUFFIXES:
        if host == suffix or host.endswith("." + suffix):
            return True
    return False


def _limitation_url_looks_soft_404(url: str, body_sample: str) -> bool:
    sample = (body_sample or "").lower()
    path = (urlparse(url).path or "").lower()
    if "404" in path or "notfound" in path or "no-such" in path or "/error/" in path:
        return True
    if not sample:
        return False
    hits = sum(1 for marker in _SOFT_404_MARKERS if marker in sample)
    return hits >= 1


def _limitation_url_access_denied(body_sample: str) -> str | None:
    sample = (body_sample or "").lower()
    if not sample:
        return None
    for marker in _ACCESS_DENIED_MARKERS:
        if marker in sample:
            return marker
    return None


def _limitation_url_verify_human_sentence(body_sample: str) -> bool:
    """
    Reject when 'verify' and 'human' appear in the same sentence.
    Sentence boundaries: . ! ? or newlines.
    """
    sample = (body_sample or "").lower()
    if not sample or "verify" not in sample or "human" not in sample:
        return False
    for sentence in _SENTENCE_SPLIT_RE.split(sample):
        s = sentence.strip()
        if not s:
            continue
        if "verify" in s and "human" in s:
            return True
    return False


def _read_limitation_response_body(response, *, content_type: str, final_url: str) -> str:
    """Read up to _LIMITATION_URL_BODY_BYTES for HTML checks; skip PDF bodies."""
    is_pdf = (
        "pdf" in (content_type or "").lower()
        or (final_url or "").lower().endswith(".pdf")
    )
    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= _LIMITATION_URL_BODY_BYTES:
                break
    finally:
        try:
            response.close()
        except Exception:
            pass
    if is_pdf:
        return ""
    raw = b"".join(chunks)[:_LIMITATION_URL_BODY_BYTES]
    return raw.decode("utf-8", errors="ignore")


def _verify_one_limitation_url(url: str) -> tuple[str | None, str | None]:
    """
    GET url and accept only clean HTTP 200 OEM/support pages.

    Rejects:
    - non-http(s) URLs
    - marketplace/retailer hosts (before and after redirects)
    - any status other than exactly 200
    - soft-404 / discontinued pages
    - access-denied / captcha / bot-wall markers on 200 HTML
    - sentences containing both 'verify' and 'human' on 200 HTML
    """
    import requests

    candidate = (url or "").strip()
    if not candidate:
        return None, "url is empty"
    if not re.match(r"^https?://", candidate, flags=re.I):
        return None, f"url is not http(s): {candidate!r}"
    if _limitation_url_is_marketplace(candidate):
        return None, f"marketplace/retailer host blocked: {candidate}"

    try:
        response = requests.get(
            candidate,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=_LIMITATION_URL_TIMEOUT_S,
            allow_redirects=True,
            stream=True,
        )
        final_url = str(response.url or candidate)
        status = int(response.status_code or 0)
        content_type = (response.headers.get("Content-Type") or "").lower()
        body = _read_limitation_response_body(
            response, content_type=content_type, final_url=final_url
        )

        if _limitation_url_is_marketplace(final_url):
            return None, f"redirected to marketplace/retailer host: {final_url}"

        # Hard rule: only HTTP 200 is acceptable.
        if status != 200:
            return None, f"GET status {status} (need 200) for {candidate}"

        if _limitation_url_looks_soft_404(final_url, body):
            return None, f"soft-404 / discontinued page for {candidate}"

        denied = _limitation_url_access_denied(body)
        if denied:
            return None, f"access-denied/bot-wall marker {denied!r} for {candidate}"

        if _limitation_url_verify_human_sentence(body):
            return None, (
                f"human-verification challenge text "
                f"('verify'+'human' same sentence) for {candidate}"
            )

        return final_url, None
    except Exception as exc:
        return None, f"GET failed for {candidate}: {type(exc).__name__}: {exc}"


def _flatten_limitation_url_buckets(urls) -> list[tuple[str, str]]:
    """Return list of (bucket, url) from typed dict or flat list."""
    out: list[tuple[str, str]] = []
    if urls is None:
        return out
    if isinstance(urls, list):
        for item in urls:
            u = str(item or "").strip()
            if u:
                out.append(("urls", u))
        return out
    if not isinstance(urls, dict):
        return out
    for bucket in _URL_BUCKET_KEYS:
        raw = urls.get(bucket)
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            continue
        for item in raw:
            u = str(item or "").strip()
            if u:
                out.append((bucket, u))
    return out


def _verify_limitation_urls(urls) -> tuple[list[str], list[str]]:
    """
    GET-check suggested limitation URLs.
    Accepts typed {home_page, product_listings, support_docs} or a flat list.
    Returns (accepted_final_urls, errors). Failed URLs are omitted, not fatal.
    Logs every accept/reject with flush so overnight Tee logs keep the trail.
    """
    pairs = _flatten_limitation_url_buckets(urls)
    accepted: list[str] = []
    errors: list[str] = []
    if not pairs:
        return accepted, errors
    if len(pairs) > _LIMITATION_URL_MAX_PER_CALL:
        msg = (
            f"urls: too many candidates ({len(pairs)}); "
            f"checking first {_LIMITATION_URL_MAX_PER_CALL} only"
        )
        errors.append(msg)
        print(f"LOG: limitation URL verify: {msg}", flush=True)
        pairs = pairs[:_LIMITATION_URL_MAX_PER_CALL]

    seen_keys: set[str] = set()
    for bucket, url in pairs:
        final_url, err = _verify_one_limitation_url(url)
        if err:
            errors.append(f"urls.{bucket}: {err}")
            print(
                f"LOG: limitation URL REJECT bucket={bucket} url={url!r} reason={err}",
                flush=True,
            )
            continue
        key = _normalize_url_key(final_url)
        if not key or key in seen_keys:
            print(
                f"LOG: limitation URL SKIP-DUP bucket={bucket} url={final_url!r}",
                flush=True,
            )
            continue
        seen_keys.add(key)
        accepted.append(final_url)
        print(
            f"LOG: limitation URL ACCEPT bucket={bucket} url={final_url!r}",
            flush=True,
        )
    return accepted, errors


def _ensure_search_limitations_dict(search_limitations) -> dict:
    if isinstance(search_limitations, dict):
        return search_limitations
    return {}


def add_limitations(
    search_limitations: dict | None,
    *,
    commercial_layer: str = "",
    sellable_unit: str = "",
    buyer: str = "",
    why_this_layer: str = "",
    companies=None,
    urls=None,
) -> dict:
    """
    Validate a search-limitations seed batch and merge accepts into memory.

    Private checkers validate commercial classification (layer + sellable_unit
    + buyer + why_this_layer), company rows (name/reason/confidence), and live
    URL availability. Successful company names and URLs are appended to
    search_limitations['companies'] / ['urls'] and cannot be altered by later
    agent calls (resubmits of accepted values are no-ops). Classification
    fields persist on search_limitations once accepted. Companies/URLs are
    refused until classification is complete. Errors are returned as strings
    for the agent to fix (orchestrator caps retries). Does not persist to
    Mongo — caller writes via create_case.

    Returns:
        {
          "search_limitations": dict,  # mutated / normalized
          "accepted_companies": [...],
          "accepted_urls": [...],
          "newly_accepted_companies": [...],
          "newly_accepted_urls": [...],
          "commercial_layer": str|None,
          "sellable_unit": str|None,
          "buyer": str|None,
          "why_this_layer": str|None,
          "errors": [str, ...],
          "ok": bool,  # True when this batch had zero errors
        }
    """
    limitations = _ensure_search_limitations_dict(search_limitations)
    companies_raw = limitations.get("companies")
    if isinstance(companies_raw, list):
        limitations["companies"] = list(companies_raw)
    elif isinstance(companies_raw, str) and companies_raw.strip():
        limitations["companies"] = [companies_raw.strip()]
    else:
        limitations["companies"] = []
    urls_raw = limitations.get("urls")
    if isinstance(urls_raw, list):
        limitations["urls"] = list(urls_raw)
    elif isinstance(urls_raw, str) and urls_raw.strip():
        limitations["urls"] = [urls_raw.strip()]
    else:
        limitations["urls"] = []

    errors: list[str] = []

    # --- commercial classification (step 1 fields) ---
    classification_submitted = any(
        str(v or "").strip()
        for v in (commercial_layer, sellable_unit, buyer, why_this_layer)
    )
    if classification_submitted:
        layer, layer_err = _normalize_commercial_layer(commercial_layer)
        unit, unit_err = _normalize_classification_text(
            sellable_unit, field="sellable_unit", min_len=3
        )
        buyer_text, buyer_err = _normalize_classification_text(
            buyer, field="buyer", min_len=3
        )
        why_text, why_err = _normalize_classification_text(
            why_this_layer, field="why_this_layer", min_len=12
        )
        for err in (layer_err, unit_err, buyer_err, why_err):
            if err:
                errors.append(err)
        if layer and unit and buyer_text and why_text:
            limitations["commercial_layer"] = layer
            limitations["sellable_unit"] = unit
            limitations["buyer"] = buyer_text
            limitations["why_this_layer"] = why_text
    elif not _commercial_classification_complete(limitations):
        # Keep any prior valid pieces; require a full classification before
        # accepting companies/urls in this or later batches.
        existing_layer = str(limitations.get("commercial_layer") or "").strip()
        if existing_layer:
            layer, layer_err = _normalize_commercial_layer(existing_layer)
            if layer:
                limitations["commercial_layer"] = layer
            elif layer_err:
                errors.append(layer_err)

    has_company_payload = companies is not None
    has_url_payload = urls is not None
    wants_companies_or_urls = has_company_payload or has_url_payload
    if wants_companies_or_urls and not _commercial_classification_complete(limitations):
        errors.append(
            "commercial classification incomplete: need commercial_layer, "
            "sellable_unit, buyer, and why_this_layer before companies/urls"
        )
        company_names, company_errors = [], []
        url_accepted, url_errors = [], []
        if has_company_payload:
            # Still surface schema issues for the agent, but do not merge.
            _, company_errors = _check_company_suggestion_entries(companies)
        if has_url_payload:
            # Skip live GET until classification is complete.
            url_errors = ["urls: skipped until commercial classification is complete"]
        errors.extend(company_errors)
        errors.extend(url_errors)
        return {
            "search_limitations": limitations,
            "accepted_companies": list(limitations.get("companies") or []),
            "accepted_urls": list(limitations.get("urls") or []),
            "newly_accepted_companies": [],
            "newly_accepted_urls": [],
            "commercial_layer": limitations.get("commercial_layer"),
            "sellable_unit": limitations.get("sellable_unit"),
            "buyer": limitations.get("buyer"),
            "why_this_layer": limitations.get("why_this_layer"),
            "errors": errors,
            "ok": False,
        }

    company_names, company_errors = _check_company_suggestion_entries(companies)
    errors.extend(company_errors)

    url_accepted, url_errors = _verify_limitation_urls(urls)
    errors.extend(url_errors)

    existing_companies = {
        _normalize_merge_text(c) for c in (limitations.get("companies") or []) if c
    }
    existing_urls = {
        _normalize_url_key(u) for u in (limitations.get("urls") or []) if u
    }

    newly_companies: list[str] = []
    for name in company_names:
        key = _normalize_merge_text(name)
        if not key or key in existing_companies:
            continue
        limitations["companies"].append(name)
        existing_companies.add(key)
        newly_companies.append(name)

    newly_urls: list[str] = []
    for url in url_accepted:
        key = _normalize_url_key(url)
        if not key or key in existing_urls:
            continue
        limitations["urls"].append(url)
        existing_urls.add(key)
        newly_urls.append(url)

    # De-dupe in place after each successful merge.
    limitations["companies"] = _fuzzy_dedupe_strings(limitations.get("companies") or [])
    limitations["urls"] = _exact_dedupe_strings(
        limitations.get("urls") or [], key_fn=_normalize_url_key
    )

    return {
        "search_limitations": limitations,
        "accepted_companies": list(limitations.get("companies") or []),
        "accepted_urls": list(limitations.get("urls") or []),
        "newly_accepted_companies": newly_companies,
        "newly_accepted_urls": newly_urls,
        "commercial_layer": limitations.get("commercial_layer"),
        "sellable_unit": limitations.get("sellable_unit"),
        "buyer": limitations.get("buyer"),
        "why_this_layer": limitations.get("why_this_layer"),
        "errors": errors,
        "ok": len(errors) == 0,
    }
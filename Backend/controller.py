import uuid
import time
import json
from datetime import datetime as dt

from sources.Gemini import *
from data_processor import *
from data_processor import *
from models.alerts import *
from models.cases import *
from models.users import *
from file_controller import *
from live_search.liveSearchController import *
from llm_brain.gemini import Gemini

"""
Controller functions for handling business logic
"""

def _bucket_error_on_analysis_failure(claims, result):
    """On thread failure: Error only for buckets that had claims but never returned."""
    if not claims:
        return None
    if result is None:
        return 'Error'
    return None

def _patent_bucket_error_kwargs(asserted_claims, independent_claims, core_claims, pivotal_claims,
                                asserted_patentResults, independent_patentResults,
                                core_patentResults, pivotal_patentResults):
    kwargs = {}
    for bucket_key, claims, result in (
        ('generic_bucket', asserted_claims, asserted_patentResults),
        ('asserted_bucket', asserted_claims, asserted_patentResults),
        ('independent_bucket', independent_claims, independent_patentResults),
        ('core_bucket', core_claims, core_patentResults),
        ('pivotal_bucket', pivotal_claims, pivotal_patentResults),
    ):
        bucket_status = _bucket_error_on_analysis_failure(claims, result)
        if bucket_status is not None:
            kwargs[bucket_key] = bucket_status
    return kwargs

def _product_bucket_error_kwargs(asserted_claims, independent_claims, core_claims, pivotal_claims,
                                 asserted_product_details_list, independent_product_details_list,
                                 core_product_details_list, pivotal_product_details_list):
    kwargs = {}
    for bucket_key, claims, result in (
        ('generic_bucket', asserted_claims, asserted_product_details_list),
        ('asserted_bucket', asserted_claims, asserted_product_details_list),
        ('independent_bucket', independent_claims, independent_product_details_list),
        ('core_bucket', core_claims, core_product_details_list),
        ('pivotal_bucket', pivotal_claims, pivotal_product_details_list),
    ):
        bucket_status = _bucket_error_on_analysis_failure(claims, result)
        if bucket_status is not None:
            kwargs[bucket_key] = bucket_status
    return kwargs

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

def is_blob_under_12mb(blob_or_size):
    """
    Check if blob or size (in bytes) is under the 16MB document limit.

    Args:
        blob_or_size: bytes/bytearray (uses len()), or int (size in bytes).

    Returns:
        bool: True if under 16 MB, False otherwise.
    """
    size_limit_bytes = 12 * 1024 * 1024  # 16 MB
    if isinstance(blob_or_size, (int, float)):
        size = int(blob_or_size)
    else:
        try:
            size = len(blob_or_size)
        except TypeError:
            return False
    return 0 <= size < size_limit_bytes

def get_risk_level(infringement_percentage):
    """
    Get the risk level for a given infringement percentage
    """
    if infringement_percentage > 0.9:
        return 'high'
    elif infringement_percentage > 0.7:
        return 'medium'
    else:
        return 'low'

def calculate_average_infringement_percentage(case):
    """
    Calculate the average infringement percentage for a list of cases
    """
    total_infringement_percentage = 0
    infringements_count = 0
    infringements = case.get('infringements', [])
    similar_claims = case.get('similar_claims', [])
    try:
        for infringement in infringements:
            claims = infringement.get('similar_claims', [])
            sum_infringement = 0
            for claim in claims:
                sum_infringement += claim.get('similarity_score', 0)
            if len(claims) != 0:
                avg_infringement = sum_infringement / len(claims)
                total_infringement_percentage += avg_infringement
                infringements_count += 1
    except Exception as e:
        print(f'Error calculating average infringement percentage for infringements: {str(e)}')
        return 0
    
    try:
        for infringement in similar_claims:
            claims = infringement.get('similar_claims', [])
            sum_infringement = 0
            for claim in claims:
                if type(claim) == dict:
                    if (claim.get('claim', '').strip() != ''):
                        sum_infringement += claim.get('similarity_score', 0)
            if len(claims) != 0:
                avg_infringement = sum_infringement / len(claims)
                total_infringement_percentage += avg_infringement
                infringements_count += 1
    except Exception as e:
        print(f'Error calculating average infringement percentage for similar claims: {str(e)}')
        return 0

    if infringements_count == 0:
        return 0
    return total_infringement_percentage / infringements_count

def get_case_infringement_chart(case_id):
    """
    Retrieve chart-ready infringement rows for a case by case_id.

    Returns ``(chart_data, error_code)``. See ``get_infringement_chart`` in
    ``models.cases`` for the full contract on possible error codes.
    """
    chart_data, patent_chart_data, product_chart_data, error_code = get_infringement_chart(case_id)
    if error_code:
        status_by_code = {
            'CASE_NOT_FOUND': 404,
            'NO_PARENT_CLAIMS': 422,
            'NO_INFRINGEMENTS': 422,
            'INFRINGEMENT_CLAIMS_MISSING': 422,
            'NO_MATCHES_ABOVE_THRESHOLD': 200,
        }
        return {
            'success': error_code == 'NO_MATCHES_ABOVE_THRESHOLD',
            'message': error_code,
            'chart_data': chart_data or [],
            'patent_chart_data': patent_chart_data or [],
            'product_chart_data': product_chart_data or [],
            'error_code': error_code,
            'status_code': status_by_code.get(error_code, 500),
        }
    return {
        'success': True,
        'message': 'Infringement chart retrieved successfully',
        'chart_data': chart_data,
        'patent_chart_data': patent_chart_data,
        'product_chart_data': product_chart_data
    }

def generate_patent_description(case_id):
    """
    Generate a description for a patent by case_id
    """
    case = get_case_by_id(case_id)
    if case is None:
        return {'success': False, 'message': 'Case not found'}
    
    document_urls = case.get('document_urls', [])
    document_contents = []
    for document in document_urls:
        content  = readDocumentFromUrl(document, headers={"X-API-KEY": getEnvKey('uspto')})
        document_contents.append(content)

    if (len(document_contents) == 0) or (document_contents is None):
        return {'success': False, 'message': 'No viable document contents provided'}
    
    complete_document_contents = ""
    for content in document_contents:
        if content.strip() != "":
            complete_document_contents = f"{complete_document_contents}\n\n{content}"
    
    if complete_document_contents.strip() == "":
        return {'success': False, 'message': 'No viable document contents provided'}

    summary = get_patent_summary(complete_document_contents)
    
    # Update Case Data for the Generated Description
    result = update_case(case_id, {'description': summary, 'last_updated': dt.now()})
    return {
        'success': True, 
        'message': 'Patent summary generated successfully', 
        'summary': summary
        }

def _claims_already_populated(claims) -> bool:
    if claims is None:
        return False
    if isinstance(claims, dict):
        return len(claims) > 0
    if isinstance(claims, list):
        return len(claims) > 0
    return False

def isolate_claims(case_id):
    """
    Isolate the claims for a given case_id
    """
    case_data = get_case_by_id(case_id)
    if case_data is None:
      print(f'\nERROR: Error getting claims: Case not found')
      return {'success': False, 'message': 'Case not found'}

    existing_claims = case_data.get('claims', [])
    if _claims_already_populated(existing_claims):
      return {'success': True, 'message': 'Claims already exist', 'claims': existing_claims}

    description = case_data.get('description', '')
    complete_document_contents = ""
    if description.strip() != "":
      complete_document_contents = f"Description:\n{description}"
    
    document_urls = case_data.get('document_urls', [])
    document_contents = []
    for document in document_urls:
      if 'uspto' in document:
        content  = readDocumentFromUrl(document, headers={"X-API-KEY": getEnvKey('uspto')})
      elif '/document/' in document:
        doc_id = document.split('/')[-1].strip()
        content = readLocalDocument(doc_id)
      else:
        content = readDocumentFromUrl(document)
      document_contents.append(content)

    documents = case_data.get('documents', [])
    for document in documents:
      if document.get('source', '') == 'uspto':
        content  = readDocumentFromUrl(document.get('url', ''), headers={"X-API-KEY": getEnvKey('uspto')})
        document_contents.append(content)
      elif document.get('source', '') == 'local':
        doc_id = document.get('url', '').split('/')[-1].strip()
        document_view = getDocumentById(doc_id)
        if document_view.get('success', False):
          document_blob = document_view.get('document', {}).get('file_content', '')
          content = document_blob.decode('utf-8')
          document_contents.append(content)
      else:
        document_contents.append(document.get('content', ''))

    if (len(document_contents) == 0) or (document_contents is None):
      return {
        'success': False, 
        'message': 'No viable document contents provided', 
        'documents': {
          'document_urls_key': document_urls,
          'documents_key': document_contents
        }}

    complete_document_contents = ""
    for content in document_contents:
      if content.strip() != "":
        complete_document_contents = f"{complete_document_contents}\n\n{content}"
    
    if complete_document_contents.strip() == "":
      print(f'\nERROR: Error getting claims: No viable document contents provided')
      return {'success': False, 'message': 'No viable document contents provided'}

    try:
      isolated = Gemini().extract_claims(patent_content=complete_document_contents)
      validated, error_message = isolated.verify_isolated_claims()
      if not validated:
        print(f'\nERROR: Error getting claims: {error_message}')
        return {'success': False, 'message': error_message}
      claims = {
        str(i): isolated.claims[i].model_dump()
        for i in range(len(isolated.claims))
      }
    except Exception as e:
      print(f'\nERROR: Error extracting claims: {str(e)}')
      return {'success': False, 'message': str(e)}

    if not claims:
      print(f'\nERROR: Error getting claims: No claims found')
      return {'success': False, 'message': 'No claims found'}

    # Update Claims in Case Data
    result = update_case(case_id, {'claims': claims, 'last_updated': dt.now()})
    if result['success']:
      return {'success': True, 'message': 'Claims updated successfully', 'claims': claims}
    else:
      print(f'\nERROR: Error updating claims: {result["message"]}')
      return {'success': False, 'message': result['message']}

def _merge_infringement_details(case_id: str, partial: dict) -> dict:
    """Merge patent/product infringement_details without clobbering parallel thread writes."""
    case = get_case_by_id(case_id) or {}
    details = dict(case.get('infringement_details') or {})
    for key, value in partial.items():
        if key in ('patent_ids', 'product_ids') and isinstance(value, dict):
            bucket_map = dict(details.get(key) or {})
            for bucket, ids in value.items():
                bucket_map[bucket] = ids
            details[key] = bucket_map
        else:
            details[key] = value
    return details


# Functions for Infringement Analysis
def start_patent_analysis(
    app,
    case_id: str,
    keywords: list[str],
    country: str,
    ref_case_title: str = '',
    ref_case_id: str = '',
    titles_to_avoid: list[str] = [],
    ids_to_avoid: list[str] = [],
    search_type: str = 'generic',
    asserted_claims: list[dict] = [], 
    independent_claims: list[dict] = [], 
    core_claims: list[dict] = [], 
    pivotal_claims: list[dict] = []
    ):
    start_time = time.time()
    if search_type == 'bucketed':
        search_status_key = "asserted_claims_patent_analysis"
    with app.app_context():
        asserted_patentResults = None
        independent_patentResults = None
        core_patentResults = None
        pivotal_patentResults = None

        asserted_created_patent_ids = []
        independent_created_patent_ids = []
        core_created_patent_ids = []
        pivotal_created_patent_ids = []
        try:
            update_infringement_analysis_flags(
                case_id=case_id, 
                category='patent'
                )

            if len(asserted_claims) > 0:
                update_infringement_analysis_status(
                    case_id=case_id,
                    asserted_bucket='Started',
                    generic_bucket='Started'
                )
                asserted_patentResults, asserted_created_patent_ids = searchPatentSources(
                    keywords=keywords, 
                    country=country, 
                    reference_claims=asserted_claims, 
                    ref_case_title=ref_case_title, 
                    ref_case_id=ref_case_id,
                    titles_to_avoid=titles_to_avoid,
                    ids_to_avoid=ids_to_avoid,
                    search_type=search_type,
                    case_id=case_id,
                    )
                update_infringement_analysis_status(
                    case_id=case_id,
                    asserted_bucket='Completed',
                    generic_bucket='Completed'
                )
            else:
                update_infringement_analysis_status(
                    case_id=case_id,
                    asserted_bucket='Error',
                    generic_bucket='Error',
                    error_message="No generic/asserted claims provided"
                )
            
            if len(independent_claims) > 0:
                update_infringement_analysis_status(
                    case_id=case_id,
                    independent_bucket='Started',
                )
                independent_patentResults, independent_created_patent_ids = searchPatentSources(
                    keywords=keywords, 
                    country=country, 
                    reference_claims=independent_claims, 
                    ref_case_title=ref_case_title, 
                    ref_case_id=ref_case_id,
                    titles_to_avoid=titles_to_avoid,
                    ids_to_avoid=ids_to_avoid,
                    search_type='independent',
                    case_id=case_id,
                    )
                update_infringement_analysis_status(
                    case_id=case_id,
                    independent_bucket='Completed',
                )
                if not independent_patentResults:
                    print(f'LOG: Case {case_id}: independent patent search returned 0 infringements')
            else:
                update_infringement_analysis_status(
                    case_id=case_id,
                    independent_bucket='Error',
                    error_message="No independent claims provided"
                )
            
            if len(core_claims) > 0:
                update_infringement_analysis_status(
                    case_id=case_id,
                    core_bucket='Started',
                )
                core_patentResults, core_created_patent_ids = searchPatentSources(
                    keywords=keywords, 
                    country=country, 
                    reference_claims=core_claims, 
                    ref_case_title=ref_case_title, 
                    ref_case_id=ref_case_id,
                    titles_to_avoid=titles_to_avoid,
                    ids_to_avoid=ids_to_avoid,
                    search_type='core',
                    case_id=case_id,
                    )
                update_infringement_analysis_status(
                    case_id=case_id,
                    core_bucket='Completed',
                )
                if not core_patentResults:
                    print(f'LOG: Case {case_id}: core patent search returned 0 infringements')
            else:
                update_infringement_analysis_status(
                    case_id=case_id,
                    core_bucket='Error',
                    error_message="No core claims provided"
                )
            
            if len(pivotal_claims) > 0:
                update_infringement_analysis_status(
                    case_id=case_id,
                    pivotal_bucket='Started',
                )
                pivotal_patentResults, pivotal_created_patent_ids = searchPatentSources(
                    keywords=keywords, 
                    country=country, 
                    reference_claims=pivotal_claims, 
                    ref_case_title=ref_case_title, 
                    ref_case_id=ref_case_id,
                    titles_to_avoid=titles_to_avoid,
                    ids_to_avoid=ids_to_avoid,
                    search_type='pivotal',
                    case_id=case_id,
                    )
                update_infringement_analysis_status(
                    case_id=case_id,
                    pivotal_bucket='Completed',
                )
                if not pivotal_patentResults:
                    print(f'LOG: Case {case_id}: pivotal patent search returned 0 infringements')
            else:
                update_infringement_analysis_status(
                    case_id=case_id,
                    pivotal_bucket='Error',
                    error_message="No pivotal claims provided"
                )
            # Avoid duplicates among all patent results
            patentResults = []
            if asserted_patentResults is not None:
                for result in asserted_patentResults:
                    if result not in patentResults:
                        patentResults.append(result)
            if independent_patentResults is not None:
                for result in independent_patentResults:
                    if result not in patentResults:
                        patentResults.append(result)
            if core_patentResults is not None:
                for result in core_patentResults:
                    if result not in patentResults:
                        patentResults.append(result)
            if pivotal_patentResults is not None:
                for result in pivotal_patentResults:
                    if result not in patentResults:
                        patentResults.append(result)
            
            if search_type != 'generic':
                search_type = "bucketed"
            update_infringements(case_id, patentResults)
            try:
                refresh_case_infringement_scores(case_id)
            except Exception as score_err:
                print(f'LOG: refresh_case_infringement_scores failed for {case_id}: {score_err}')
            infringement_details = _merge_infringement_details(case_id, {
                'patent_ids': {
                    'asserted': asserted_created_patent_ids,
                    'independent': independent_created_patent_ids,
                    'core': core_created_patent_ids,
                    'pivotal': pivotal_created_patent_ids,
                },
                'search_keywords': keywords,
                'claim_type': search_type,
            })
            end_time = time.time()
            time_in_seconds = end_time - start_time
            time_in_minutes = time_in_seconds // 60
            time_in_hours = int(time_in_minutes // 60)
            time_in_seconds = round(time_in_seconds % 60, 2)
            time_in_minutes = int(time_in_minutes % 60)
            update_infringement_analysis_flags(
                case_id=case_id, 
                category='patent', 
                update_type='completed',
                time_taken=f"{time_in_hours}h {time_in_minutes}m {time_in_seconds}s"
                )
            update_case(
                case_id,
                {
                    'infringement_details': infringement_details
                },
            )
        except Exception as e:
            current_time = time.time()
            time_in_seconds = current_time - start_time
            time_in_minutes = time_in_seconds // 60
            time_in_hours = int(time_in_minutes // 60)
            time_in_seconds = round(time_in_seconds % 60, 2)
            time_in_minutes = int(time_in_minutes % 60)
            update_infringement_analysis_status(
                case_id,
                update_type="patent",
                status='Error',
                **_patent_bucket_error_kwargs(
                    asserted_claims, independent_claims, core_claims, pivotal_claims,
                    asserted_patentResults, independent_patentResults,
                    core_patentResults, pivotal_patentResults,
                ),
            )
            update_infringement_analysis_flags(
                case_id=case_id, 
                category='patent', 
                update_type='error',
                error_message=str(e),
                time_taken=f"{time_in_hours}h {time_in_minutes}m {time_in_seconds}s"
                )
            print(f'\nERROR: LiveSearch: Error performing infringement analysis: {str(e)}')

def start_product_analysis(
    app,
    case_id: str,
    keywords: list[str],
    owners: list[str],
    search_limitations: list[dict],
    asserted_claims: list[dict] = [], 
    independent_claims: list[dict] = [], 
    core_claims: list[dict] = [], 
    pivotal_claims: list[dict] = [],
    search_type: str = 'generic'
    ):
    with app.app_context():
        start_time = time.time()
        asserted_product_details_list = None
        independent_product_details_list = None
        core_product_details_list = None
        pivotal_product_details_list = None

        asserted_created_product_ids = []
        independent_created_product_ids = []
        core_created_product_ids = []
        pivotal_created_product_ids = []
        try:
            update_infringement_analysis_flags(
                case_id=case_id, 
                category='product'
                )
            
            if len(asserted_claims) > 0:
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    asserted_bucket='Started',
                    generic_bucket='Started'
                )
                asserted_product_details_list, asserted_created_product_ids = searchProductSources(
                    keywords=keywords, 
                    owners=owners, 
                    reference_claims=asserted_claims, 
                    search_limitations=search_limitations,
                    parent_case_id=case_id,
                    )
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    asserted_bucket='Completed',
                    generic_bucket='Completed'
                )
            else:
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    asserted_bucket='Error',
                    generic_bucket='Error',
                    error_message="No generic/asserted claims provided"
                )
            
            if len(independent_claims) > 0:
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    independent_bucket='Started',
                )
                independent_product_details_list, independent_created_product_ids = searchProductSources(
                    keywords=keywords, 
                    owners=owners, 
                    reference_claims=independent_claims, 
                    search_limitations=search_limitations,
                    parent_case_id=case_id,
                    )
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    independent_bucket='Completed',
                )
            else:
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    independent_bucket='Error',
                    error_message="No independent claims provided"
                )
            
            if len(core_claims) > 0:
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    core_bucket='Started',
                )
                core_product_details_list, core_created_product_ids = searchProductSources(
                    keywords=keywords, 
                    owners=owners, 
                    reference_claims=core_claims, 
                    search_limitations=search_limitations,
                    parent_case_id=case_id,
                    )
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    core_bucket='Completed',
                )
            else:
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    core_bucket='Error',
                    error_message="No core claims provided"
                )
            
            if len(pivotal_claims) > 0:
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    pivotal_bucket='Started',
                )
                pivotal_product_details_list, pivotal_created_product_ids = searchProductSources(
                    keywords=keywords, 
                    owners=owners, 
                    reference_claims=pivotal_claims, 
                    search_limitations=search_limitations,
                    parent_case_id=case_id,
                    )
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    pivotal_bucket='Completed',
                )
            else:
                update_infringement_analysis_status(
                    case_id=case_id,
                    update_type="product",
                    pivotal_bucket='Error',
                    error_message="No pivotal claims provided"
                )
                    
            productResults = []
            if asserted_product_details_list is not None:
                for result in asserted_product_details_list:
                    if result not in productResults:
                        productResults.append(result)
            if independent_product_details_list is not None:
                for result in independent_product_details_list:
                    if result not in productResults:
                        productResults.append(result)
            if core_product_details_list is not None:
                for result in core_product_details_list:
                    if result not in productResults:
                        productResults.append(result)
            if pivotal_product_details_list is not None:
                for result in pivotal_product_details_list:
                    if result not in productResults:
                        productResults.append(result)

            update_infringements(case_id, productResults)
            try:
                refresh_case_infringement_scores(case_id)
            except Exception as score_err:
                print(f'LOG: refresh_case_infringement_scores failed for {case_id}: {score_err}')
            infringement_details = _merge_infringement_details(case_id, {
                'product_ids': {
                    'asserted': asserted_created_product_ids,
                    'independent': independent_created_product_ids,
                    'core': core_created_product_ids,
                    'pivotal': pivotal_created_product_ids
                },
                'search_keywords': keywords,
                'claim_type': search_type,
            })
            end_time = time.time()
            time_in_seconds = end_time - start_time
            time_in_minutes = time_in_seconds // 60
            time_in_hours = int(time_in_minutes // 60)
            time_in_seconds = round(time_in_seconds % 60, 2)
            time_in_minutes = int(time_in_minutes % 60)
            update_infringement_analysis_flags(
                case_id=case_id, 
                category='product', 
                update_type='completed',
                time_taken=f"{time_in_hours}h {time_in_minutes}m {time_in_seconds}s"
                )
            update_case(
                case_id,
                {
                    'infringement_details': infringement_details
                },
            )
        except Exception as e:
            print(f'\nERROR: LiveSearch: Error performing product sourceinfringement analysis: {str(e)}')
            end_time = time.time()
            time_in_seconds = end_time - start_time
            time_in_minutes = time_in_seconds // 60
            time_in_hours = int(time_in_minutes // 60)
            time_in_seconds = round(time_in_seconds % 60, 2)
            time_in_minutes = int(time_in_minutes % 60)
            update_infringement_analysis_status(
                case_id,
                update_type="product",
                status='Error',
                **_product_bucket_error_kwargs(
                    asserted_claims, independent_claims, core_claims, pivotal_claims,
                    asserted_product_details_list, independent_product_details_list,
                    core_product_details_list, pivotal_product_details_list,
                ),
            )
            update_infringement_analysis_flags(
                case_id=case_id, 
                category='product', 
                update_type='error',
                error_message=str(e),
                time_taken=f"{time_in_hours}h {time_in_minutes}m {time_in_seconds}s"
                )

# Function to fetch Patent by ID with multiple sources
def fetchById(app, patent_id:str, user_id:str):
    uspto_error = False
    google_error = False
    free_patents_error = False
    error_message = ""
    with app.app_context():
        try:
            uspto_instance = USPTOPatentAPI(api_key=getEnvKey('uspto'))
            uspto_data = uspto_instance.get_complete_patent_info(patent_id)
            if uspto_data is None:
                uspto_error = True
                raise Exception("No Data found through USPTO")
            else:
                uspto_data['created_by'] = user_id
                uspto_data['_id'] = f"uspto_{user_id}_{patent_id}"
                uspto_data['keywords'] = getKeywordsFromPatent(uspto_data['documents'])
                print(f'\nUSPTO Data: {json.dumps(uspto_data, indent=4)}')
                creationResult = create_case(uspto_data)
                print(f"TEST 1.1: Creation Result: {json.dumps(creationResult, indent=4)}")
                descriptionResult = generate_patent_description(f"uspto_{user_id}_{patent_id}")
                print(f"TEST 1.2: Description Generation Result: {json.dumps(descriptionResult, indent=4)}")
                claimsResult = isolate_claims(f"uspto_{user_id}_{patent_id}")
                print(f"TEST 1.3: Claims Isolation Result: {json.dumps(claimsResult, indent=4)}")
                remove_patent_from_fetching_list(user_id, patent_id)
                remove_patent_from_error_list(user_id, patent_id)
                returnValue = {
                    'success': True,
                    'message': 'Patent data imported successfully',
                    'case_id': f"uspto_{user_id}_{patent_id}",
                    'keywords': uspto_data.get('keywords', []),
                    'case_data': uspto_data
                }
                return returnValue, 200
        except Exception as e:
            print(f'\nError getting patent data from USPTO: {str(e)}')
            uspto_error = True
            error_message = str(e)
        # Try searching patent id using Google Patents
        if uspto_error:
            time.sleep(180)
            try:
                google_patents = GooglePatents()
                google_patents_details = google_patents.search_by_id(patent_id)
                if google_patents_details is not None:
                    if isinstance(google_patents_details, dict):
                        case_data = passToGeminiForMetadata(
                            google_patents_details.get('metadata_content', ''),
                            claims_content=google_patents_details.get('claims_content'),
                        ).model_dump()
                    else:
                        case_data = passToGeminiForMetadata(str(google_patents_details)).model_dump()
                    if case_data is not None:
                        patent_page_url = google_patents.get_patent_page_url(patent_id)
                        if patent_page_url:
                            case_data['document_urls'] = [patent_page_url]
                            case_data['documents'] = [
                                {'url': patent_page_url, 'source': 'google_patents'}
                            ]
                        case_data['source'] = 'google_patents'
                        case_data['_id'] = f"googlepatents_{user_id}_{patent_id}"
                        case_data['created_by'] = user_id
                        if case_data.get('current_status', '') == '':
                            case_data['current_status'] = 'Granted'
                        case_data['created_date'] = dt.now().strftime('%Y-%m-%d')
                        created_id = case_data.get('_id', '')
                        creationResult = create_case(case_data)
                        print(f"TEST 2.1: Creation Result: {json.dumps(creationResult, indent=4)}")
                        created_id = case_data.get('_id', '')
                        if 'DocumentCreationError' in created_id:
                            raise Exception("Document Creation Error")
                        descriptionResult = generate_patent_description(f"googlepatents_{user_id}_{patent_id}")
                        print(f"TEST 2.2: Description Generation Result: {json.dumps(descriptionResult, indent=4)}")
                        claimsResult = isolate_claims(f"googlepatents_{user_id}_{patent_id}")
                        print(f"TEST 2.3: Claims Isolation Result: {json.dumps(claimsResult, indent=4)}")
                        remove_patent_from_fetching_list(user_id, patent_id)
                        remove_patent_from_error_list(user_id, patent_id)
                        returnValue = {
                            'success': True,
                            'message': 'Patent data imported successfully',
                            'case_id': created_id,
                            'keywords': case_data.get('keywords', []),
                            'case_data': case_data
                        }
                        return returnValue, 200
                else:
                    raise Exception("No Data found through Google Patents")
            except Exception as e:
                print(f"ERROR: Error getting patent details from Google Patents: {str(e)}")
                error_message = str(e)
                google_error = True
        # Patent not found using Google Patents, try using Free Patents Online
        if google_error and uspto_error:
            time.sleep(180)
            try:
                free_patents = FreePatentsOnline()
                free_patents_details = free_patents.search_by_id(patent_id)
                if free_patents_details is not None:
                    case_data = passToGeminiForMetadata(str(free_patents_details)).model_dump()
                    if case_data is not None:
                        case_data['source'] = 'free_patents_online'
                        case_data['_id'] = f"freepatentsonline_{user_id}_{patent_id}"
                        case_data['created_by'] = user_id
                        if case_data.get('current_status', '') == '':
                            case_data['current_status'] = 'Granted'
                        case_data['created_date'] = dt.now().strftime('%Y-%m-%d')
                        creationResult = create_case(case_data)
                        print(f"TEST 3.1: Creation Result: {json.dumps(creationResult, indent=4)}")
                        created_id = case_data.get('_id', '')
                        if 'DocumentCreationError' in created_id:
                            returnValue = {'success': False, 'message': created_id}
                            raise Exception("Document Creation Error")
                        descriptionResult = generate_patent_description(f"freepatentsonline_{user_id}_{patent_id}")
                        print(f"TEST 3.2: Description Generation Result: {json.dumps(descriptionResult, indent=4)}")
                        claimsResult = isolate_claims(f"freepatentsonline_{user_id}_{patent_id}")
                        print(f"TEST 3.3: Claims Isolation Result: {json.dumps(claimsResult, indent=4)}")
                        remove_patent_from_error_list(user_id, patent_id)
                        remove_patent_from_fetching_list(user_id, patent_id)
                        returnValue = {
                            'success': True,
                            'message': 'Patent data imported successfully',
                            'case_id': created_id,
                            'keywords': case_data.get('keywords', []),
                            'case_data': case_data
                        }
                        return returnValue, 200
                else:
                    raise Exception("No Data found through Free Patents Online")
            except Exception as e:
                print(f"ERROR: Error getting patent details from Free Patents Online: {str(e)}")
                error_message = str(e)
                set_patent_to_error_list(user_id, patent_id, error_message)
                free_patents_error = True

        errorReturn = {
            'success': False,
            'message': f"Failed to find patent with ID {patent_id}",
            'error_message': error_message
        }
        set_patent_to_error_list(user_id, patent_id, error_message)
        return errorReturn, 500

def bulk_fetch_by_ids(app, patent_ids: list[str], records: list[list[str]], user_id: str):
    """
    Bulk fetch patents by IDs
    """
    with app.app_context():
        error_list = []
        try:
            for record in records:
                if len(record) >= 2:
                    patent_id, title = record[0], record[1]
                    last_entry = (patent_id == patent_ids[-1])
                    if type(patent_id) == float:
                        patent_id = int(patent_id)               
                    patent_id = str(patent_id).strip().replace('.', '')
                    print(f"Patent ID: {patent_id}, Title: {title}")
                    response, _ = fetchById(app, patent_id, user_id)
                    responseSuccess= response.get('success', False)
                    if (not responseSuccess):
                        error_list.append(patent_id)
                    if last_entry:
                        update_user_fetching_patents(user_id, [], error_list, replace=True)
            return {
                'success': True,
                'message': f"Patents bulk fetched successfully"
            }
        except Exception as e:
            print(f"ERROR: Error bulk fetching patents: {str(e)}")
            return {
                'success': False,
                'message': f"Error bulk fetching patents: {str(e)}"
            }

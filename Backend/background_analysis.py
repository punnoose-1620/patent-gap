import time
from datetime import datetime as dt

from live_search.liveSearchController import searchPatentSources, searchProductSources
from models.cases import get_case_by_id, update_case, update_infringements


def format_execution_time(start_time):
  current_time = time.time()
  time_in_seconds = current_time - start_time
  time_in_minutes = time_in_seconds // 60
  time_in_hours = int(time_in_minutes // 60)
  time_in_seconds = time_in_seconds % 60
  time_in_minutes = int(time_in_minutes % 60)
  return f"{time_in_hours}h {time_in_minutes}m {time_in_seconds}s"


def validate_infringement_analysis_inputs(case_id, data):
  if data is None:
    return {'success': False, 'message': 'No data provided'}, 400
  if case_id is None:
    return {'success': False, 'message': 'Case ID is required'}, 400

  case_data = get_case_by_id(case_id)
  if case_data is None:
    return {'success': False, 'message': 'Case not found'}, 404

  if 'claims' not in data:
    return {'success': False, 'message': 'Claims are required'}, 400
  if 'owners' not in data:
    return {'success': False, 'message': 'Owners are required'}, 400
  if 'country' not in data:
    return {'success': False, 'message': 'Country is required'}, 400

  keywords = data.get('keywords', [])
  ref_claims = data.get('claims', [])
  owners = data.get('owners', [])

  if (keywords is None) or (len(keywords) == 0):
    return {'success': False, 'message': 'Keywords are required'}, 400
  if (ref_claims is None) or (len(ref_claims) == 0):
    return {'success': False, 'message': 'Claims are required'}, 400
  if (owners is None) or (len(owners) == 0):
    return {'success': False, 'message': 'Owners are required'}, 400

  return {
    'case_data': case_data,
    'keywords': keywords,
    'owners': owners,
    'ref_claims': ref_claims,
    'country': data.get('country', ''),
    'search_limitations': data.get('search_limitations', {})
  }, 200


def run_infringement_analysis_for_case(case_id, data):
  """
  Run the infringement analysis flow for a case.

  This is shared by the live API route and the Render cron placeholder route so
  the long-running work is not tied to a browser/session-specific endpoint.
  """
  validated, status_code = validate_infringement_analysis_inputs(case_id, data)
  if status_code != 200:
    print(f"\nERROR: BackgroundAnalysis: {validated.get('message')}")
    return validated, status_code

  keywords = validated['keywords']
  owners = validated['owners']
  ref_claims = validated['ref_claims']
  country = validated['country']
  search_limitations = validated['search_limitations']

  start_time = time.time()
  update_case(case_id, {'infringement_analysis_status': 'Started', 'last_updated': dt.now()})

  try:
    patent_results = searchPatentSources(keywords, country, ref_claims)
    infringement_update = update_infringements(case_id, patent_results)
    print(f"LOG: BackgroundAnalysis: Patent infringement update result: {infringement_update}")
    case_update = update_case(case_id, {
      'infringements': patent_results,
      'infringement_analysis_status': 'Patent Sources Completed',
      'last_updated': dt.now()
    })
    print(f"LOG: BackgroundAnalysis: Patent status update result: {case_update}")
  except Exception as e:
    update_case(case_id, {'infringement_analysis_status': 'Failed during Patent Sources', 'last_updated': dt.now()})
    print(f'\nERROR: BackgroundAnalysis: Error performing patent source infringement analysis: {str(e)}')
    return {
      'success': False,
      'message': f'Error performing patent source infringement analysis: {str(e)}',
      'execution_time': format_execution_time(start_time)
    }, 500

  try:
    product_details_list = searchProductSources(keywords, owners, ref_claims, search_limitations)
    infringement_update = update_infringements(case_id, product_details_list)
    print(f"LOG: BackgroundAnalysis: Product infringement update result: {infringement_update}")
    case_update = update_case(case_id, {
      'infringement_analysis_status': 'Product Sources Completed',
      'last_updated': dt.now()
    })
    print(f"LOG: BackgroundAnalysis: Product status update result: {case_update}")
    completed_update = update_case(case_id, {'infringement_analysis_status': 'Completed', 'last_updated': dt.now()})
    print(f"LOG: BackgroundAnalysis: Completed status update result: {completed_update}")
    return {
      'success': True,
      'message': 'Infringement analysis completed - Product Sources, Patent Sources',
      'execution_time': format_execution_time(start_time)
    }, 200
  except Exception as e:
    update_case(case_id, {'infringement_analysis_status': 'Failed during Product Sources', 'last_updated': dt.now()})
    print(f'\nERROR: BackgroundAnalysis: Error performing product source infringement analysis: {str(e)}')
    return {
      'success': False,
      'message': f'Error performing product source infringement analysis: {str(e)}',
      'search_results': product_details_list if 'product_details_list' in locals() else [],
      'execution_time': format_execution_time(start_time)
    }, 500

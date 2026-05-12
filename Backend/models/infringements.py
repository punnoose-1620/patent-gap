from datetime import datetime, timezone

from database import *
from env_controller import getInfringementDatabaseName


def _collection_name():
    return getInfringementDatabaseName()


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _stringify_id(document):
    if document and '_id' in document and hasattr(document['_id'], '__str__'):
        document['_id'] = str(document['_id'])
    return document


def _stringify_ids(documents):
    for document in documents:
        _stringify_id(document)
    return documents


def _build_created_at_query(start_date=None, end_date=None):
    if start_date is None and end_date is None:
        return None

    created_at_query = {}
    if start_date is not None:
        created_at_query['$gte'] = start_date
    if end_date is not None:
        created_at_query['$lte'] = end_date
    return created_at_query


def get_infringement_by_id(infringement_id):
    infringement = getDataById(connect_to_database(), _collection_name(), infringement_id)
    if infringement is not None:
        return {
            'success': True,
            'message': 'Infringement fetched successfully',
            'infringement': infringement,
        }
    return {
        'success': False,
        'message': 'Failed to fetch infringement',
    }


def get_infringements_by_ids(infringement_ids):
    if not infringement_ids:
        return {
            'success': True,
            'message': 'Infringements fetched successfully',
            'infringements': [],
        }

    try:
        collection = connect_to_database()[_collection_name()]
        documents = list(
            collection.find({'_id': {'$in': list(infringement_ids)}}, max_time_ms=120000)
        )
        _stringify_ids(documents)
        by_id = {document['_id']: document for document in documents}
        ordered = [by_id[infringement_id] for infringement_id in infringement_ids if infringement_id in by_id]
        return {
            'success': True,
            'message': 'Infringements fetched successfully',
            'infringements': ordered,
        }
    except Exception as e:
        print(f'Error fetching infringements by IDs from {_collection_name()}: {e}')
        return {
            'success': False,
            'message': 'Failed to fetch infringements',
            'infringements': [],
        }


def get_infringements_by_created_date(start_date=None, end_date=None, parent_case_id=None):
    query = {}
    created_at_query = _build_created_at_query(start_date, end_date)
    if created_at_query is not None:
        query['created_at'] = created_at_query
    if parent_case_id is not None:
        query['parent_case_id'] = parent_case_id

    try:
        collection = connect_to_database()[_collection_name()]
        documents = list(collection.find(query, max_time_ms=120000).sort('created_at', -1))
        _stringify_ids(documents)
        return {
            'success': True,
            'message': 'Infringements fetched successfully',
            'infringements': documents,
        }
    except Exception as e:
        print(f'Error fetching infringements by created date from {_collection_name()}: {e}')
        return {
            'success': False,
            'message': 'Failed to fetch infringements',
            'infringements': [],
        }


def get_infringements_by_parent_case_id(parent_case_id):
    infringements = getDataByKeyValue(
        connect_to_database(),
        _collection_name(),
        'parent_case_id',
        parent_case_id,
    )
    return {
        'success': True,
        'message': 'Infringements fetched successfully',
        'infringements': infringements,
    }


def create_infringement(infringement_data):
    payload = dict(infringement_data or {})
    if not payload.get('created_at'):
        payload['created_at'] = _utc_now_iso()

    added_id = addDataById(connect_to_database(), _collection_name(), payload)
    if 'DocumentCreationError' not in added_id:
        payload['_id'] = added_id
        return {
            'success': True,
            'message': 'Infringement created successfully',
            'infringement_id': added_id,
            'infringement': payload,
        }
    return {
        'success': False,
        'message': 'Failed to create infringement',
        'input_data': infringement_data,
        'added_id': added_id,
    }


def create_infringements(infringements_data):
    if not infringements_data:
        return {
            'success': True,
            'message': 'No infringements to create',
            'infringement_ids': [],
            'infringements': [],
            'failures': [],
        }

    created_ids = []
    created_infringements = []
    failures = []

    for infringement_data in infringements_data:
        result = create_infringement(infringement_data)
        if result.get('success'):
            created_ids.append(result['infringement_id'])
            created_infringements.append(result.get('infringement'))
        else:
            failures.append({
                'input_data': infringement_data,
                'message': result.get('message'),
                'added_id': result.get('added_id'),
            })

    return {
        'success': len(failures) == 0,
        'message': 'Infringements created successfully' if not failures else 'Some infringements failed to create',
        'infringement_ids': created_ids,
        'infringements': created_infringements,
        'failures': failures,
    }


def update_infringement_by_id(infringement_id, update_data):
    updated = updateDataById(connect_to_database(), _collection_name(), update_data, infringement_id)
    if updated:
        return {
            'success': True,
            'message': 'Infringement updated successfully',
        }
    return {
        'success': False,
        'message': 'Failed to update infringement',
    }


def delete_infringement_by_id(infringement_id):
    deleted = deleteDataById(connect_to_database(), _collection_name(), infringement_id)
    if deleted:
        return {
            'success': True,
            'message': 'Infringement deleted successfully',
            'infringement_id': infringement_id,
        }
    return {
        'success': False,
        'message': 'Failed to delete infringement',
    }

import time
from models.cases import *
# from data_processor import *
from data_processor import getEmbeddingsFromDocuments, getSimilarityScore
from database import *
from env_controller import getAlertDatabaseName

alerts = [
    {
        "alert_id": '01',
        "triggered_by": 'case_001',
        "triggered_at": '2025-01-01',
        "alert_users": ['user_001', 'user_002', 'user_003'],
        "opened_receipts": ['user_001', 'user_002', 'user_003'],
        "sent_receipts": ['user_001', 'user_002', 'user_003'],
    },
    {
        "alert_id": '02',
        "triggered_by": 'case_002',
        "triggered_at": '2025-02-14',
        "alert_users": ['user_004', 'user_007'],
        "opened_receipts": ['user_004'],
        "sent_receipts": ['user_004', 'user_007'],
    },
    {
        "alert_id": '03',
        "triggered_by": 'case_003',
        "triggered_at": '2024-12-31',
        "alert_users": ['user_005'],
        "opened_receipts": [],
        "sent_receipts": ['user_005'],
    },
    {
        "alert_id": '04',
        "triggered_by": 'case_002',
        "triggered_at": '2025-03-02',
        "alert_users": ['user_001', 'user_005', 'user_010'],
        "opened_receipts": ['user_005', 'user_010'],
        "sent_receipts": ['user_001', 'user_005', 'user_010'],
    },
    {
        "alert_id": '05',
        "triggered_by": 'case_004',
        "triggered_at": '2024-10-10',
        "alert_users": ['user_003', 'user_008'],
        "opened_receipts": ['user_003'],
        "sent_receipts": ['user_003', 'user_008'],
    },
    {
        "alert_id": '06',
        "triggered_by": 'case_005',
        "triggered_at": '2024-08-08',
        "alert_users": ['user_002', 'user_004', 'user_009'],
        "opened_receipts": [],
        "sent_receipts": ['user_002', 'user_004', 'user_009'],
    }
]

def add_to_alerts(triggered_by, triggered_at, alert_users, title, description):
    newAlert = {
        "_id": str(int(time.time())),
        'title': title,
        'description': description,
        "triggered_by": triggered_by,
        "triggered_at": triggered_at,
        "alert_users": alert_users,
        "opened_receipts": [],
        "sent_receipts": []
    }
    addDataById(connect_to_database(), getAlertDatabaseName(), newAlert)
    # alerts.append(newAlert)
    # trigger_alert(alert_users)
    # return newAlert['_id']
    return newAlert['_id']

def get_alerts():
    return getAllData(connect_to_database(), getAlertDatabaseName())
    return alerts

def get_alerts_for_user(user_id):
    user_alerts = []
    my_cases = get_case_related_to_user(user_id)
    # Isolate Alerts that are related to the user
    try:
        for alert in getAllData(connect_to_database(), getAlertDatabaseName()):
            if user_id in alert['alert_users']:
                # Get Embeddings for reference case from alert's 'triggered_by' case
                triggered_by_case = get_case_by_id(alert['triggered_by'])
                triggered_by_embeddings = triggered_by_case.get('embeddings', [])
                if len(triggered_by_embeddings) == 0:
                    # If embeddings are not available, get them from the documents
                    documents = get_documents_from_case(triggered_by_case['_id'])
                    triggered_by_embeddings = getEmbeddingsFromDocuments(documents)
                max_similarity = 0
                max_similarity_case = None
                # Find IDs and similarity scores for user's cases similar to the alert case
                for case in my_cases:
                    embeddings = case.get('embeddings', [])
                    print('Embeddings:', embeddings)
                    if len(embeddings) == 0:
                        # If embeddings are not available, get them from the documents
                        documents = get_documents_from_case(case['_id'])
                        embeddings = getEmbeddingsFromDocuments(documents)
                    # Get similarity score for the case with the alert case
                    similarity_score = getSimilarityScore(embeddings, triggered_by_embeddings)
                    if similarity_score > max_similarity:
                        max_similarity = similarity_score
                        max_similarity_case = case['_id']
                    alert['similar_case'] = max_similarity_case
                    alert['similarity_score'] = max_similarity
            user_alerts.append(alert)
    except Exception as e:
        print(f"Error in get_alerts_for_user: {str(e)}")
    return user_alerts

def trigger_alert(alert_users):
    # TODO: Implement actual alert triggering logic to send alerts to the users
    return True

def create_alert(user_id, case_id, references):
    case_data = get_case_by_id(case_id)
    alert_users = [user_id]
    print('Case data: ', case_data)
    if (case_data is not None) and (case_data is not {}):
      case_data['references'] = references
      update_case(case_id, case_data)
      print('References updated')
      case_keys = case_data.keys()
      if 'created_by' in case_keys:
        if case_data['created_by'] == user_id:
          alert_users.append(case_data['created_by'])
      if 'assigned_to' in case_keys:
        if case_data['assigned_to'] == user_id:
          alert_users.append(case_data['assigned_to'])
      if 'accepted_by' in case_keys:
        if case_data['accepted_by'] == user_id:
          alert_users.append(case_data['accepted_by'])
    print('Alert Users:', alert_users)
    newAlertId = add_to_alerts(
        triggered_by=user_id, 
        triggered_at=datetime.now().strftime('%Y-%m-%d'), 
        alert_users=alert_users,
        title=f'{case_data.get("title")}',
        description=f'{len(references)} potential infringements found...'
        )
    return newAlertId
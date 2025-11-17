import time
from models.cases import *
from data_processor import *

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

def add_to_alerts(triggered_by, triggered_at, alert_users):
    newAlert = {
        "_id": str(int(time.time())),
        "triggered_by": triggered_by,
        "triggered_at": triggered_at,
        "alert_users": alert_users,
        "opened_receipts": [],
        "sent_receipts": []
    }
    alerts.append(newAlert)
    trigger_alert(alert_users)
    return newAlert['_id']

def get_alerts():
    return alerts

def get_alerts_for_user(user_id):
    user_alerts = []
    my_cases = get_case_related_to_user(user_id)
    # Isolate Alerts that are related to the user
    try:
        for alert in alerts:
            if user_id in alert['alert_users']:
                # Get Embeddings for reference case from alert's 'triggered_by' case
                triggered_by_case = get_case_by_id(alert['triggered_by'])
                triggered_by_embeddings = triggered_by_case.get('embeddings', [])
                if len(triggered_by_embeddings) == 0:
                    # If embeddings are not available, get them from the documents
                    documents = get_documents_from_case(triggered_by_case['id'])
                    triggered_by_embeddings = getEmbeddingsFromDocuments(documents)
                max_similarity = 0
                max_similarity_case = None
                # Find IDs and similarity scores for user's cases similar to the alert case
                for case in my_cases:
                    embeddings = case.get('embeddings', [])
                    print('Embeddings:', embeddings)
                    if len(embeddings) == 0:
                        # If embeddings are not available, get them from the documents
                        documents = get_documents_from_case(case['id'])
                        embeddings = getEmbeddingsFromDocuments(documents)
                    # Get similarity score for the case with the alert case
                    similarity_score = getSimilarityScore(embeddings, triggered_by_embeddings)
                    if similarity_score > max_similarity:
                        max_similarity = similarity_score
                        max_similarity_case = case['id']
                    alert['similar_case'] = max_similarity_case
                    alert['similarity_score'] = max_similarity
            user_alerts.append(alert)
    except Exception as e:
        print(f"Error in get_alerts_for_user: {str(e)}")
    return user_alerts

def trigger_alert(alert_users):
    # TODO: Implement actual alert triggering logic to send alerts to the users
    return True
import re
from database import *
from env_controller import getSearchHistoryDatabaseName, getCaseDatabaseName

def get_search_history(user_id):
    all_history = getDataByKeyValue(connect_to_database(), getSearchHistoryDatabaseName(), 'created_by', user_id)
    return all_history

def add_search_history(user_id, search_query, results):
    print(f"Adding search history for user {user_id} with query {search_query} and results {results}")
    new_history = {
        'created_by': user_id,
        'search_query': search_query,
        'search_results': results
    }
    addedId = addDataById(connect_to_database(), getSearchHistoryDatabaseName(), new_history)
    if 'DocumentCreationError' in addedId:
        return False
    if 'error' in addedId.lower():
        return False
    return True

def search_cases(search_query, user_id):
    print(f"Searching cases for query {search_query}")
    results = searchDataForKeywords(
        connect_to_database(), 
        getCaseDatabaseName(), 
        'created_by', 
        user_id, 
        search_query)
    return results
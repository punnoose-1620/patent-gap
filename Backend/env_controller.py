import os
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

production = 'prod'
development = 'dev'
testing = 'test'

# Functions to get environment variables
def getEnvKey(key):
    # Load environment variables
    load_dotenv()

    if key == 'uspto':
        return os.environ.get('USPTO_API_KEY')
    elif key == 'openai':
        return os.environ.get('OPENAI_API_KEY')
    elif key == 'gemini':
        return os.environ.get('GEMINI_API_KEY')
    elif key == 'google':
        return os.environ.get('GOOGLE_API_KEY')
    elif key == 'google_cse':
        return os.environ.get('GOOGLE_CSE_ID')
    elif key == 'apify':
        return os.environ.get('APIFY_API_KEY')
    elif key == 'serpapi':
        return os.environ.get('SERPAPI_API_KEY')
    elif key == 'ebay_client_id':
        return os.environ.get('EBAY_CLIENT_ID')
    elif key == 'ebay_client_secret':
        return os.environ.get('EBAY_CLIENT_SECRET')
    elif key == 'bestbuy':
        return os.environ.get('BESTBUY_API_KEY')
    elif key == 'walmart_client_id':
        return os.environ.get('WALMART_CLIENT_ID')
    elif key == 'walmart_client_secret':
        return os.environ.get('WALMART_CLIENT_SECRET')
    elif key == 'proxy_urls':
        return os.environ.get('PROXY_URLS')
    elif key == 'use_apify_fallback':
        return os.environ.get('USE_APIFY_FALLBACK')
    else:
        return None

def getBaseUrl():
    load_dotenv()
    return os.environ.get('BASE_URL')

def getDatabaseConnectionString():
    # Load environment variables
    load_dotenv()

    return os.environ.get('PYTHON_MONGODB_CONNECT_STRING')

def getCaseDatabaseName():
    # Load environment variables
    load_dotenv()
    
    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('CASE_DATABASE_NAME_PROD')
    elif environment == development:
        return os.environ.get('CASE_DATABASE_NAME_DEV')
    elif environment == testing:
        return os.environ.get('CASE_DATABASE_NAME_TEST')
    else:
        return os.environ.get('CASE_DATABASE_NAME_DEV')

def getAlertDatabaseName():
    # Load environment variables
    load_dotenv()
    
    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('ALERT_DATABASE_NAME_PROD')
    elif environment == development:
        return os.environ.get('ALERT_DATABASE_NAME_DEV')
    elif environment == testing:
        return os.environ.get('ALERT_DATABASE_NAME_TEST')
    else:
        return os.environ.get('ALERT_DATABASE_NAME_DEV')

def getDemoDatabaseName():
    # Load environment variables
    load_dotenv()
    
    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('DEMO_DATABASE_NAME_PROD')
    elif environment == development:
        return os.environ.get('DEMO_DATABASE_NAME_DEV')
    elif environment == testing:
        return os.environ.get('DEMO_DATABASE_NAME_TEST')
    else:
        return os.environ.get('DEMO_DATABASE_NAME_DEV')

def getUserDatabaseName():
    # Load environment variables
    load_dotenv()
    
    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('USERS_DATABASE_NAME_PROD')
    elif environment == development:
        return os.environ.get('USERS_DATABASE_NAME_DEV')
    elif environment == testing:
        return os.environ.get('USERS_DATABASE_NAME_TEST')
    else:
        return os.environ.get('USERS_DATABASE_NAME_DEV')

def getDocumentDatabaseName():
    # Load environment variables
    load_dotenv()
    
    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('DOCUMENTS_DATABASE_NAME_PROD')
    elif environment == development:
        return os.environ.get('DOCUMENTS_DATABASE_NAME_DEV')
    elif environment == testing:
        return os.environ.get('DOCUMENTS_DATABASE_NAME_TEST')
    else:
        return os.environ.get('DOCUMENTS_DATABASE_NAME_DEV')

def getInfringementDatabaseName():
    # Load environment variables
    load_dotenv()

    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('INFRINGEMENT_DATABASE_NAME_PROD')
    elif environment == development:
        return os.environ.get('INFRINGEMENT_DATABASE_NAME_DEV')
    elif environment == testing:
        return os.environ.get('INFRINGEMENT_DATABASE_NAME_TEST')
    else:
        return os.environ.get('INFRINGEMENT_DATABASE_NAME_DEV')

def getSearchHistoryDatabaseName():
    # Load environment variables
    load_dotenv()
    
    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('SEARCH_HISTORY_DATABASE_NAME_PROD')
    elif environment == development:
        return os.environ.get('SEARCH_HISTORY_DATABASE_NAME_DEV')
    elif environment == testing:
        return os.environ.get('SEARCH_HISTORY_DATABASE_NAME_TEST')
    else:
        return os.environ.get('SEARCH_HISTORY_DATABASE_NAME_DEV')

def getFolderDatabaseName():
    # Load environment variables
    load_dotenv()
    
    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('FOLDER_DATABASE_NAME_PROD')
    elif environment == development:
        return os.environ.get('FOLDER_DATABASE_NAME_DEV')
    elif environment == testing:
        return os.environ.get('FOLDER_DATABASE_NAME_TEST')
    else:
        return os.environ.get('FOLDER_DATABASE_NAME_DEV')

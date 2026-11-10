import os
from dotenv import load_dotenv

production = 'prod'
development = 'dev'
testing = 'test'

# Placeholder / unset markers commonly left in .env files.
_UNSET_SECRET_VALUES = frozenset({
    '',
    'none',
    'null',
    'nil',
    'undefined',
    'n/a',
    'na',
    '-',
    '.',
})


def normalize_env_secret(value):
    """
    Treat empty / placeholder secrets as unset.

    Returns None when the value is missing or a non-key placeholder
    (None, '', 'none', 'null', etc.) so callers can skip primary API
    paths and use backups without making a doomed request.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    cleaned = value.strip()
    if cleaned.lower() in _UNSET_SECRET_VALUES:
        return None
    return cleaned


def hasEnvKey(key):
    """True when getEnvKey(key) yields a usable secret."""
    return bool(getEnvKey(key))


# Functions to get environment variables
def getEnvKey(key):
    # Load environment variables
    load_dotenv()

    if key == 'uspto':
        raw = os.environ.get('USPTO_API_KEY')
    elif key == 'openai':
        raw = os.environ.get('OPENAI_API_KEY')
    elif key == 'gemini':
        raw = os.environ.get('GEMINI_API_KEY')
    elif key == 'google':
        raw = os.environ.get('GOOGLE_API_KEY')
    elif key == 'google_cse':
        raw = os.environ.get('GOOGLE_CSE_ID')
    elif key == 'apify':
        raw = os.environ.get('APIFY_API_KEY')
    else:
        return None
    return normalize_env_secret(raw)

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


def getAuditDatabaseName():
    # Load environment variables
    load_dotenv()

    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('AUDIT_DATABASE_NAME_PROD') or 'audit'
    elif environment == development:
        return os.environ.get('AUDIT_DATABASE_NAME_DEV') or 'audit_dev'
    elif environment == testing:
        return os.environ.get('AUDIT_DATABASE_NAME_TEST') or 'audit_test'
    else:
        return os.environ.get('AUDIT_DATABASE_NAME_DEV') or 'audit_dev'


def getChromaPersistDir():
    load_dotenv()
    configured = os.environ.get('CHROMA_PERSIST_DIR')
    if configured:
        return configured
    backend_root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(backend_root, 'vector_store')


def getAiWorkflowMode():
    load_dotenv()
    mode = (os.environ.get('AI_WORKFLOW_MODE') or 'rag').strip().lower()
    return mode if mode in ('legacy', 'rag') else 'rag'


def getGeminiEmbeddingModel():
    load_dotenv()
    return os.environ.get('GEMINI_EMBEDDING_MODEL') or 'text-embedding-004'
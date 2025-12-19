import os
from dotenv import load_dotenv

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
    else:
        return None

def getDatabaseConnectionString():
    # Load environment variables
    load_dotenv()
    
    environment = os.environ.get('ENVIRONMENT')
    if environment == production:
        return os.environ.get('DATABASE_CONNECTION_STRING_PROD')
    elif environment == development:
        return os.environ.get('DATABASE_CONNECTION_STRING_DEV')
    elif environment == testing:
        return os.environ.get('DATABASE_CONNECTION_STRING_TEST')
    else:
        return os.environ.get('DATABASE_CONNECTION_STRING_DEV')

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
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

def getBaseUrl():
    load_dotenv()
    return os.environ.get('BASE_URL')

def getDatabaseConnectionString():
    # Load environment variables
    load_dotenv()

    return os.environ.get('PYTHON_MONGODB_CONNECT_STRING')
    
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


def getEmailConfig(key):
    """
    Return email-related env configuration values based on key.

    Supported keys:
    - source_email
    - app_password
    - smtp_host
    - smtp_port
    - use_tls
    - confirmation_url
    """
    load_dotenv()

    if key == 'source_email':
        return os.environ.get('GMAIL_SENDER_EMAIL')
    elif key in ('app_password', 'api_secret'):
        return os.environ.get('GMAIL_APP_PASSWORD')
    elif key == 'smtp_host':
        return os.environ.get('GMAIL_SMTP_HOST', 'smtp.gmail.com')
    elif key == 'smtp_port':
        value = os.environ.get('GMAIL_SMTP_PORT', '587')
        try:
            return int(value)
        except ValueError:
            return 587
    elif key == 'use_tls':
        value = os.environ.get('GMAIL_USE_TLS', 'true').strip().lower()
        return value in ('1', 'true', 'yes', 'y', 'on')
    elif key == 'confirmation_url':
        return os.environ.get('EMAIL_CONFIRMATION_URL', 'https://patentgap.ai/')

    return None

def getEmailSenderAddress():
    load_dotenv()
    return os.environ.get('GMAIL_SENDER_EMAIL')

def getGmailAppPassword():
    load_dotenv()
    return os.environ.get('GMAIL_APP_PASSWORD')

def getGmailSmtpHost():
    load_dotenv()
    return os.environ.get('GMAIL_SMTP_HOST', 'smtp.gmail.com')

def getGmailSmtpPort():
    load_dotenv()
    value = os.environ.get('GMAIL_SMTP_PORT', '587')
    try:
        return int(value)
    except ValueError:
        return 587

def getGmailUseTls():
    load_dotenv()
    value = os.environ.get('GMAIL_USE_TLS', 'true').strip().lower()
    return value in ('1', 'true', 'yes', 'y', 'on')

def getEmailConfirmationUrl():
    load_dotenv()
    return os.environ.get('EMAIL_CONFIRMATION_URL', 'https://patentgap.ai/')

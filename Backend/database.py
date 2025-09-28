import os
from firebase_admin import credentials, initialize_app, db
from dotenv import load_dotenv

def connect_to_database ():
    """
    Reads connection strings from .env file and connects to Firebase database.
    Returns the Firebase app instance.
    """
    # Load environment variables from .env file
    load_dotenv()

    # Get Firebase credentials and database URL from environment variables
    firebase_creds_path = os.getenv('FIREBASE_CREDENTIALS')
    firebase_db_url = os.getenv('FIREBASE_DATABASE_URL')

    if not firebase_creds_path or not firebase_db_url:
        raise ValueError("FIREBASE_CREDENTIALS and FIREBASE_DATABASE_URL must be set in .env file.")

    # Initialize Firebase app if not already initialized
    if not len(initialize_app._apps):
        cred = credentials.Certificate(firebase_creds_path)
        app = initialize_app(cred, {
            'databaseURL': firebase_db_url
        })
    else:
        app = initialize_app.get_app()

    return app

def getAllData(app, collectionName):
    """
    Fetches all data from a specified Firebase Realtime Database collection.

    Args:
        app: The initialized Firebase app instance.
        collectionName (str): The name of the collection (database path) to fetch.

    Returns:
        dict: All data from the specified collection, or None if not found.
    """
    ref = db.reference(collectionName, app=app)
    data = ref.get()
    return data

def getDataById(app, collectionName, entryId):
    """
    Fetches a specific entry by ID from a given Firebase Realtime Database collection.

    Args:
        app: The initialized Firebase app instance.
        collectionName (str): The name of the collection (database path) to fetch from.
        entryId (str): The ID of the entry to retrieve.

    Returns:
        dict: The data for the specified entry, or None if not found.
    """
    ref = db.reference(f"{collectionName}/{entryId}", app=app)
    data = ref.get()
    return data

def updateDataById(app, collectionName, entryData):
    """
    Updates a specific entry in a Firebase Realtime Database collection by its ID.

    Args:
        app: The initialized Firebase app instance.
        collectionName (str): The name of the collection (database path) to update.
        entryData (dict): The data to update, must include the entry's 'id' key.

    Returns:
        bool: True if update was successful, False otherwise.
    """
    entry_id = entryData.get('_id')
    if not entry_id:
        raise ValueError("entryData must include an 'id' key for the entry to update.")

    # Remove 'id' from the data to avoid overwriting the key itself
    update_fields = {k: v for k, v in entryData.items() if k != 'id'}
    if not update_fields:
        # Nothing to update
        return False

    ref = db.reference(f"{collectionName}/{entry_id}", app=app)
    ref.update(update_fields)
    return True

def deleteDataById(app, collectionName, entryId):
    """
    Deletes a specific entry by ID from a given Firebase Realtime Database collection.

    Args:
        app: The initialized Firebase app instance.
        collectionName (str): The name of the collection (database path) to delete from.
        entryId (str): The ID of the entry to delete.

    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    ref = db.reference(f"{collectionName}/{entryId}", app=app)
    if ref.get() is None:
        return False  # Entry does not exist
    ref.delete()
    return True

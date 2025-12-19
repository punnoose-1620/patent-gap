import os
from datetime import datetime
from google.cloud import storage
from pymongo import MongoClient
from typing import Optional, Dict, Any, List
from env_controller import getDatabaseConnectionString

import firebase_admin
from firebase_admin import credentials, firestore

# Module-level variable to store MongoDB database instance
_mongodb_client = None
_mongodb_db = None

def connect_to_database():
    """
    Connects to Firestore using MongoDB connection string from environment variables.
    Returns the MongoDB database client.
    
    The connection string should be in the format:
    mongodb://<username>:<password>@<host>:<port>/<database>?<options>
    
    Returns:
        Database: MongoDB database instance for the 'patent-gap' database
        
    Raises:
        ValueError: If MONGODB_CONNECTION_STRING is not set in .env file
    """
    global _mongodb_client, _mongodb_db

    
    # Get MongoDB connection string from environment
    connection_string = getDatabaseConnectionString()
    # print('\nConnection String: ', connection_string)
    
    if not connection_string:
        raise ValueError("MONGODB_CONNECTION_STRING must be set in .env file.")
    
    # Connect if not already connected
    if _mongodb_client is None:
        try:
            _mongodb_client = MongoClient(connection_string)
            # Test the connection
            _mongodb_client.admin.command('ping')

            # Get the database (database name is typically in the connection string)
            # Extract database name from connection string or use default
            db_name = 'patent-gap'  # Default, or extract from connection string
            _mongodb_db = _mongodb_client[db_name]
            # print('\nDatabase: ', _mongodb_db)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MongoDB/Firestore: {e}")
    
    return _mongodb_db

def getCollectionsFromDatabase(db):
    """
    Fetches all collections from a MongoDB database.
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        
    Returns:
        list: List of all collections in the database.
    """
    try:
        # print('\nDb : ', db)
        collections = db.list_collection_names()
        return collections
    except Exception as e:
        print(f"Error fetching collections from database: {e}")
        return []

def checkCollectionExists(db, collectionName):
    """
    Checks if a collection exists in a MongoDB database.
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        collectionName (str): The name of the collection to check.
    """
    return collectionName in getCollectionsFromDatabase(db)

def createCollection(db, collectionName):
    """
    Creates a new collection in a MongoDB database.
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        collectionName (str): The name of the collection to create.
    """
    try:
        collection = db.create_collection(collectionName)
        return collection
    except Exception as e:
        print(f"Error creating collection {collectionName}: {e}")
        return None

def getAllData(db, collectionName):
    """
    Fetches all data from a specified Firestore collection.
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        collectionName (str): The name of the collection to fetch.
        
    Returns:
        list: List of all documents in the collection, or empty list if collection doesn't exist.
    """
    try:
        collection = db[collectionName]
        # Convert ObjectId to string for JSON serialization
        documents = list(collection.find({}))
        # Convert _id from ObjectId to string if present
        for doc in documents:
            if '_id' in doc and hasattr(doc['_id'], '__str__'):
                doc['_id'] = str(doc['_id'])
        return documents
    except Exception as e:
        print(f"Error fetching all data from {collectionName}: {e}")
        return []

def deleteAllData(db, collectionName):
    """
    Deletes all data from a specified Firestore collection.
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        collectionName (str): The name of the collection to delete.
    """
    try:
        return db[collectionName].delete_many({})
    except Exception as e:
        print(f"Error deleting all data from {collectionName}: {e}")
        return False

def getDataById(db, collectionName, entryId):
    """
    Fetches a specific entry by ID from a Firestore collection.
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        collectionName (str): The name of the collection to fetch from.
        entryId (str): The ID of the entry to retrieve.
        
    Returns:
        dict: The data for the specified entry, or None if not found.
    """
    try:
        collection = db[collectionName]
        document = collection.find_one({'_id': entryId})
        if document is None:
            allDocs = collection.find({})
            for doc in allDocs:
                if doc['_id'] == entryId or doc['id'] == entryId:
                    document = doc
                    break
        
        # Convert ObjectId to string if present
        if document and '_id' in document and hasattr(document['_id'], '__str__'):
            document['_id'] = str(document['_id'])
        
        return document
    except Exception as e:
        print(f"Error fetching data by ID from {collectionName}: {e}")
        return None

def updateDataById(db, collectionName, entryData):
    """
    Updates a specific entry in a Firestore collection by its ID.
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        collectionName (str): The name of the collection to update.
        entryData (dict): The data to update, must include the entry's '_id' key.
        
    Returns:
        bool: True if update was successful, False otherwise.
    """
    try:
        entry_id = entryData.get('_id')
        if not entry_id:
            raise ValueError("entryData must include an '_id' key for the entry to update.")
        
        # Remove '_id' from the data to avoid overwriting the key itself
        update_fields = {k: v for k, v in entryData.items() if k != '_id'}
        if not update_fields:
            # Nothing to update
            return False
        
        collection = db[collectionName]
        result = collection.update_one(
            {'_id': entry_id},
            {'$set': update_fields}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating data by ID in {collectionName}: {e}")
        return False

def deleteDataById(db, collectionName, entryId):
    """
    Deletes a specific entry by ID from a Firestore collection.
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        collectionName (str): The name of the collection to delete from.
        entryId (str): The ID of the entry to delete.
        
    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    try:
        collection = db[collectionName]
        result = collection.delete_one({'_id': entryId})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting data by ID from {collectionName}: {e}")
        return False

def addDataById(db, collectionName, entryData):
    """
    Adds a new entry to a Firestore collection.
    If '_id' is provided in entryData, uses that; otherwise MongoDB generates one.
    If entry data already exists under different '_id', one of the following happens:
    - if all the keys and values are the same, do nothing
    - if any key which didn't exist (or was None/empty) has a new value, update the existing entry with the new value
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        collectionName (str): The name of the collection to add to.
        entryData (dict): The data to insert. May include '_id' to specify the document ID.
        
    Returns:
        str: The inserted document ID (as string)
    """
    try:
        if not checkCollectionExists(db, collectionName):
            createCollection(db, collectionName)
        collection = db[collectionName]
        allData = getAllData(db, collectionName)
        if '_id' not in entryData.keys():
            entryData['_id'] = str(int(datetime.now().timestamp()))
        
        # tempEntry = entryData.copy()
        # tempEntry.pop('_id')
        # for data in allData:
            data.pop('_id')
            if data == tempEntry:
                keys = tempEntry.keys()
                update = False
                for key in keys:
                    if (data[key] is None or data[key] == '') and (entryData[key] is not None and entryData[key] != ''):
                        update = True
                        data[key] = entryData[key]
                if update:
                    if updateDataById(db, collectionName, entryData):
                        return str(data['_id'])
                else:
                    return None
        
        result = collection.insert_one(entryData)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error adding data to {collectionName}: {e}")
        return None

def insertOrUpdateDataById(db, collectionName, entryData):
    """
    Inserts a new document or updates if it already exists (upsert operation).
    
    Args:
        db: MongoDB database instance (from connect_to_database())
        collectionName (str): The name of the collection.
        entryData (dict): The data to insert/update, must include '_id' key.
        
    Returns:
        str: The document ID
    """
    try:
        if not checkCollectionExists(db, collectionName):
            createCollection(db, collectionName)
        entry_id = entryData.get('_id')
        if not entry_id:
            raise ValueError("entryData must include an '_id' key.")
        
        collection = db[collectionName]
        collection.replace_one(
            {'_id': entry_id},
            entryData,
            upsert=True  # Insert if doesn't exist, update if it does
        )
        return str(entry_id)
    except Exception as e:
        print(f"Error inserting/updating data in {collectionName}: {e}")
        return None

def connect_to_bucket(bucketName):
    """
    Connects to a Google Cloud Storage bucket and returns the bucket instance.

    Args:
        bucketName (str): The name of the GCP bucket to connect to.

    Returns:
        google.cloud.storage.bucket.Bucket: The bucket instance.
    """
    # Assumes GOOGLE_APPLICATION_CREDENTIALS is set in the environment
    client = storage.Client()
    bucket = client.bucket(bucketName)
    return bucket

def uploadToGcpBucket(bucketName, sourceFile, destinationBlob):
    """
    Uploads a file to a Google Cloud Storage bucket.

    Args:
        bucketName (str): The name of the GCP bucket.
        sourceFile (str): The local path to the file to upload.
        destinationBlob (str): The destination path (blob name) in the bucket.

    Returns:
        bool: True if upload was successful, False otherwise.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucketName)
        blob = bucket.blob(destinationBlob)
        blob.upload_from_filename(sourceFile)
        # Return the URL to the file as 'bucket-name/file-name'
        return f"{bucketName}/{destinationBlob}"
    except Exception as e:
        print(f"Error uploading file to bucket: {e}")
        return None

def loadFromGcpBucket(bucketName, fileName):
    """
    Loads a specific file from a Google Cloud Storage bucket into memory.

    Args:
        bucketName (str): The name of the GCP bucket.
        fileName (str): The name/path of the file (blob) in the bucket.

    Returns:
        bytes: The file content as bytes if successful, None otherwise.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucketName)
        blob = bucket.blob(fileName)
        if not blob.exists():
            print(f"File '{fileName}' does not exist in bucket '{bucketName}'.")
            return None
        file_content = blob.download_as_bytes()
        return file_content
    except Exception as e:
        print(f"Error loading file from bucket: {e}")
        return None

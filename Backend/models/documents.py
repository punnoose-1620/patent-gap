from database import *
from env_controller import getDocumentDatabaseName

def getAllDocuments():
    all_documents = getAllData(connect_to_database(), getDocumentDatabaseName())
    return all_documents

def createDocument(document_data):
    addedId = addDataById(connect_to_database(), getDocumentDatabaseName(), document_data)
    if addedId is not None:
        document_data['_id'] = addedId
        return {
            'success': True,
            'message': 'Document created successfully',
            'document_id': addedId
        }
    return {
        'success': False,
        'message': 'Failed to create document'
    }

def updateDocument(document_id, update_data):
    updated = updateDataById(connect_to_database(), getDocumentDatabaseName(), update_data, document_id)
    if updated:
        return {
            'success': True,
            'message': 'Document updated successfully'
        }
    return {
        'success': False,
        'message': 'Failed to update document'
    }

def deleteDocument(document_id):
    deleted = deleteDataById(connect_to_database(), getDocumentDatabaseName(), document_id)
    if deleted:
        return {
            'success': True,
            'message': 'Document deleted successfully',
            'document_id': document_id
        }
    return {
        'success': False,
        'message': 'Failed to delete document'
    }

def getDocumentById(document_id):
    document = getDataById(connect_to_database(), getDocumentDatabaseName(), document_id)
    if document is not None:
        return {
            'success': True,
            'message': 'Document fetched successfully',
            'document': document
        }
    return {
        'success': False,
        'message': 'Failed to fetch document'
    }

def getDocumentsByCaseId(case_id):
    documents = getAllData(connect_to_database(), getDocumentDatabaseName(), {'case_id': case_id})
    if documents is not None:
        return {
            'success': True,
            'message': 'Documents fetched successfully',
            'documents': documents
        }
    return {
        'success': False,
        'message': 'Failed to fetch documents'
    }

def getDocumentsByUserId(user_id):
    documents = getAllData(connect_to_database(), getDocumentDatabaseName(), {'created_by': user_id})
    if documents is not None:
        return {
            'success': True,
            'message': 'Documents fetched successfully',
            'documents': documents
        }
    return {
        'success': False,
        'message': 'Failed to fetch documents'
    }
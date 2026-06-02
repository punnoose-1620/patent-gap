import json
from database import *
from datetime import datetime, date
from env_controller import getUserDatabaseName

mock_users = [
    {
        "full_name": "Alice Johnson",
        "id": "user_001",
        "_id": "user_001",
        "title": "Ms.",
        "role": "client",
        "cases": ["case_001"],
        "patents": ["patent_001"],
        "created_on": "2023-12-01",
        "deleted_on": None,
        "email": "alice.johnson@example.com",
        "password": "alicepass"
    },
    {
        "full_name": "Bob Smith",
        "id": "user_002",
        "_id": "user_002",
        "title": "Mr.",
        "role": "attorney",
        "cases": ["case_001", "case_002"],
        "patents": ["patent_002", "patent_003"],
        "created_on": "2023-11-15",
        "deleted_on": None,
        "email": "bob.smith@example.com",
        "password": "bobpass"
    }
]

def create_user(data):
    """
    Create a new user
    
    Args:
        data (dict): User data
    
    Returns:
    """
    addedId = addDataById(connect_to_database(), getUserDatabaseName(), data)
    if addedId is not None:
        data['_id'] = addedId
        return {
            'success': True,
            'message': 'User created successfully',
            'user_id': data['_id']
        }
    return {
        'success': False,
        'message': 'Failed to create user'
    }

def update_user(data, user_id):
    """
    Update a user's information
    
    Args:
        data (dict): User data
    """
    updated = updateDataById(
        connect_to_database(), 
        getUserDatabaseName(), 
        data, 
        user_id
        )
    if updated:
        return {
            'success': True,
            'message': 'User updated successfully',
            'user_id': data.get('_id', None)
        }
    return {
        'success': False,
        'message': 'Failed to update user'
    }

def login_user(email, password):
    """
    Authenticate user login
    
    Args:
        email (str): User's email address
        password (str): User's password
    
    Returns:
        dict: Result containing success status, message, and user_id if successful
    """
    if not email or not password:
        return {
            'success': False,
            'message': 'Email and password are required'
        }
    
    users = getAllData(connect_to_database(), getUserDatabaseName())
    for user in users:
        print(f'LOG: User found: {user}')
        if user['email'] == email and user['password'] == password:
            return {
                'success': True,
                'message': 'Login successful',
                'user_id': user.get('_id', None),
                'email': email
            }
        elif user['email'] == email:
            return {
                'success': False,
                'message': 'Invalid password'
            }
    return {
        'success': False,
        'message': 'Login failed',
        'user_id': user.get('_id', None),
        'email': email
    }

def does_user_exist(email):
    """
    Check if a user exists by email
    
    Args:
        email (str): User's email address
    """
    users = getAllData(connect_to_database(), getUserDatabaseName())
    for user in users:
        if user['email'] == email:
            return True
    return False

def get_user_profile(user_id, show_password=False):
    """
    Get user profile information
    
    Args:
        user_id (str): User's unique identifier
    
    Returns:
        dict: User profile data
    """
    user = getDataById(connect_to_database(), getUserDatabaseName(), user_id)
    if user is not None:
        user_copy = user.copy()
        if 'password' in user_copy and not show_password:
            del user_copy['password']
        if isinstance(user_copy.get('last_updated'), (datetime, date)):
            user_copy['last_updated'] = user_copy['last_updated'].isoformat()
        return user_copy
    return None

def verify_password(user_id, entered_password):
    """
    Verify if the entered password matches the user's current password.

    Args:
        user_id (str): User's unique identifier
        entered_password (str): Password to verify

    Returns:
        bool: True if password matches, False otherwise
    """
    user = getDataById(connect_to_database(), getUserDatabaseName(), user_id)
    if user is not None:
        return user.get('password') == entered_password
    return False

def change_password(user_id, new_password):
    """
    Change the password for a user.

    Args:
        user_id (str): User's unique identifier
        new_password (str): The new password to set

    Returns:
        dict: Result containing success status and message
    """
    user = getDataById(connect_to_database(), getUserDatabaseName(), user_id)
    if user is not None:
        updateDataById(connect_to_database(), getUserDatabaseName(), {'password': new_password}, user_id)
        return {
            'success': True,
            'message': 'Password updated successfully'
        }
    return {
        'success': False,
        'message': 'User not found'
    }

def update_user_fetching_patents(
    user_id: str,
    fetching_patents: list[str],
    error_patents: list[str],
    replace: bool = False
) -> dict:
    """
    Replace the user's bulk-import progress lists.

    Args:
        user_id: User's _id in the users collection
        fetching_patents: Patent IDs currently being fetched
        error_patents: Patent IDs that failed to import

    Returns:
        dict with success status and message
    """
    print(
        f'LOG: Updating user {user_id} fetching patents: '
        f'{fetching_patents} error patents: {error_patents}'
    )

    user = getDataById(connect_to_database(), getUserDatabaseName(), user_id)
    if user is None:
        return {
            'success': False,
            'message': 'User not found',
        }

    if not replace:
        # If replace is False, append new values to existing list without duplicates
        existing_fetching_patents = user.get('fetching_patents', [])
        existing_error_patents = user.get('error_patents', [])
        for value in existing_fetching_patents:
            if value in fetching_patents:
                fetching_patents.remove(value)
        for value in existing_error_patents:
            if value in error_patents:
                error_patents.remove(value)
        fetching_patents = existing_fetching_patents + [str(p).strip() for p in fetching_patents if str(p).strip()]
        error_patents = existing_error_patents + [str(p).strip() for p in error_patents if str(p).strip()]
    response = update_user(
        {
            'fetching_patents': [str(p).strip() for p in fetching_patents if str(p).strip()],
            'error_patents': [str(p).strip() for p in error_patents if str(p).strip()],
        },
        user_id,
    )
    return response

def remove_patent_from_fetching_list(user_id: str, patent_id: str) -> dict:
    """
    Remove a patent from the user's fetching list.
    """
    user = getDataById(connect_to_database(), getUserDatabaseName(), user_id)
    if user is None:
        return {
            'success': False,
            'message': 'User not found',
        }
    existing_fetching_patents = user.get('fetching_patents', [])
    error_patents = user.get('error_patents', [])
    if patent_id in existing_fetching_patents:
        existing_fetching_patents.remove(patent_id)
    return update_user_fetching_patents(user_id, existing_fetching_patents, error_patents, replace=True)

def remove_patent_from_error_list(user_id: str, patent_id: str) -> dict:
    """
    Remove a patent from the user's fetching errors list.
    """
    user = getDataById(connect_to_database(), getUserDatabaseName(), user_id)
    if user is None:
        return {
            'success': False,
            'message': 'User not found',
        }
    error_patents = user.get('error_patents', [])
    fetching_patents = user.get('fetching_patents', [])
    if patent_id in error_patents:
        error_patents.remove(patent_id)
    return update_user_fetching_patents(user_id, fetching_patents, error_patents, replace=True)

def set_patent_to_error_list(user_id: str, patent_id: str) -> dict:
    """
    Set a patent to the user's error list.
    """
    user = getDataById(connect_to_database(), getUserDatabaseName(), user_id)
    if user is None:
        return {
            'success': False,
            'message': 'User not found',
        }
    existing_error_patents = user.get('error_patents', [])
    existing_fetching_patents = user.get('fetching_patents', [])
    if patent_id not in existing_error_patents:
        existing_error_patents.append(patent_id)
    if patent_id in existing_fetching_patents:
        existing_fetching_patents.remove(patent_id)
    return update_user_fetching_patents(user_id, existing_fetching_patents, existing_error_patents, replace=True)
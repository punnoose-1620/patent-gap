import json
from database import *
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
    updated = updateDataById(connect_to_database(), getUserDatabaseName(), data, user_id)
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
        print(f'LOG: User found: {json.dumps(user, indent=4)}')
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
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

def get_user_profile(user_id):
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
        if 'password' in user_copy:
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
        user['password'] = new_password
        updateDataById(connect_to_database(), getUserDatabaseName(), user)
        return {
            'success': True,
            'message': 'Password updated successfully'
        }
    return {
        'success': False,
        'message': 'User not found'
    }
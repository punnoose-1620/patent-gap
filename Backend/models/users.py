mock_users = [
    {
        "full_name": "Alice Johnson",
        "id": "user_001",
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
        "title": "Mr.",
        "role": "attorney",
        "cases": ["case_001", "case_002"],
        "patents": ["patent_002", "patent_003"],
        "created_on": "2023-11-15",
        "deleted_on": None,
        "email": "bob.smith@example.com",
        "password": "bobpass"
    },
    {
        "full_name": "Carol Lee",
        "id": "user_003",
        "title": "Dr.",
        "role": "client",
        "cases": ["case_002"],
        "patents": ["patent_004"],
        "created_on": "2024-01-10",
        "deleted_on": None,
        "email": "carol.lee@example.com",
        "password": "carolpass"
    },
    {
        "full_name": "David Kim",
        "id": "user_004",
        "title": "Mr.",
        "role": "attorney",
        "cases": ["case_003"],
        "patents": ["patent_005"],
        "created_on": "2023-10-20",
        "deleted_on": None,
        "email": "david.kim@example.com",
        "password": "davidpass"
    },
    {
        "full_name": "Eva Green",
        "id": "user_005",
        "title": "Ms.",
        "role": "client",
        "cases": ["case_001", "case_003"],
        "patents": ["patent_006", "patent_007"],
        "created_on": "2024-02-05",
        "deleted_on": None,
        "email": "eva.green@example.com",
        "password": "evapass"
    },
    {
        "full_name": "Frank Miller",
        "id": "user_006",
        "title": "Mr.",
        "role": "attorney",
        "cases": ["case_002", "case_003"],
        "patents": ["patent_008"],
        "created_on": "2023-09-30",
        "deleted_on": None,
        "email": "frank.miller@example.com",
        "password": "frankpass"
    },
    {
        "full_name": "Grace Chen",
        "id": "user_007",
        "title": "Dr.",
        "role": "client",
        "cases": [],
        "patents": [],
        "created_on": "2024-03-01",
        "deleted_on": None,
        "email": "grace.chen@example.com",
        "password": "gracepass"
    },
    {
        "full_name": "Henry Brown",
        "id": "user_008",
        "title": "Mr.",
        "role": "attorney",
        "cases": ["case_001"],
        "patents": ["patent_009"],
        "created_on": "2023-08-12",
        "deleted_on": None,
        "email": "henry.brown@example.com",
        "password": "henrypass"
    },
    {
        "full_name": "Ivy Wilson",
        "id": "user_009",
        "title": "Ms.",
        "role": "client",
        "cases": ["case_003"],
        "patents": ["patent_010"],
        "created_on": "2024-01-22",
        "deleted_on": None,
        "email": "ivy.wilson@example.com",
        "password": "ivypass"
    },
    {
        "full_name": "Jack Davis",
        "id": "user_010",
        "title": "Mr.",
        "role": "attorney",
        "cases": [],
        "patents": [],
        "created_on": "2023-07-05",
        "deleted_on": None,
        "email": "jack.davis@example.com",
        "password": "jackpass"
    }
]

def login_user(email, password):
    """
    Authenticate user login
    
    Args:
        email (str): User's email address
        password (str): User's password
    
    Returns:
        dict: Result containing success status, message, and user_id if successful
    """
    # TODO: Implement actual authentication logic
    # For now, using mock authentication
    if not email or not password:
        return {
            'success': False,
            'message': 'Email and password are required'
        }
    
    # Mock authentication - replace with actual database lookup
    for user in mock_users:
        if user['email'] == email and user['password'] == password:
            return {
                'success': True,
                'message': 'Login successful',
                'user_id': user.get('id', None),
                'email': email
            }
    return {
        'success': False,
        'message': 'Invalid email or password'
    }

def get_user_profile(user_id):
    """
    Get user profile information
    
    Args:
        user_id (str): User's unique identifier
    
    Returns:
        dict: User profile data
    """
    for user in mock_users:
        if '_id' in user.keys():
            if (user['_id'] == user_id):
                user_copy = user.copy()
                if 'password' in user_copy:
                    del user_copy['password']
                return user_copy
        if 'id' in user.keys():
            if (user['id'] == user_id):
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
    for user in mock_users:
        if user['_id'] == user_id:
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
    for user in mock_users:
        if user['_id'] == user_id:
            user['password'] = new_password
            return {
                'success': True,
                'message': 'Password updated successfully'
            }
    return {
        'success': False,
        'message': 'User not found'
    }

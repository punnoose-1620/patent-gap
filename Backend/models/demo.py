import datetime

demo_requests = [
    {
        "id": "request_001",
        "name": "John Doe",
        "email": "john.doe@example.com",
        "organization": "Example Inc.",
        "role": "Client",
        "date": "2023-01-01",
        "time": "10:00",
        "timezone": "UTC"
    }
]

def create_demo_request(name, email, organization, role, date, time, timezone):
    try:
        demo_requests.append({
            "id": f"{role}_{int(timezone.datetime.now().timestamp())}",
            "name": name,
            "email": email,
            "organization": organization,
            "role": role,
            "date": date,
            "time": time,
            "timezone": timezone
        })
        return {
            "success": True,
            "message": "Demo request created successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Demo request creation failed: {str(e)}"
        }

def get_demo_requests():
    return demo_requests

def create_demo_request(name, email, organization, role, date, time, timezone):
    """
    Create a new demo request
    
    Args:
        name (str): Full name of the requester
        email (str): Email address of the requester
        organization (str): Organization name
        role (str): Role or title of the requester
        date (str): Preferred date for the demo
        time (str): Preferred time for the demo
        timezone (str): Time zone for the demo
    
    Returns:
        dict: Result containing success status and request details
    """
    
    if not all([name, email, organization, role, date, time, timezone]):
        return {
            'success': False,
            'message': 'All fields are required'
        }
    
    # Generate a mock request ID
    import uuid
    request_id = f"demo_req_{str(uuid.uuid4())[:8]}"
    
    # Mock storage (in real implementation, save to database)
    demo_request = {
        '_id': request_id,
        'name': name,
        'email': email,
        'organization': organization,
        'role': role,
        'date': date,
        'time': time,
        'timezone': timezone,
        'status': 'pending',
        'created_at': datetime.datetime.utcnow().isoformat() + 'Z'  # Use current UTC timestamp
    }
    
    return {
        'success': True,
        'message': 'Demo request submitted successfully',
        'request_id': request_id,
        'demo_request': demo_request
    }

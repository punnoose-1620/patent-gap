"""
Swagger configuration and models for Patent Gap API
"""

from flasgger import Swagger

# Swagger configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/swagger/"
}

# Swagger template configuration
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Patent Gap API",
        "description": "API for Patent Gap Management System - A comprehensive system for managing patent cases and analysis",
        "version": "1.0.0",
        "contact": {
            "name": "Patent Gap Team",
            "email": "support@patentgap.com"
        }
    },
    "host": "localhost:5000",
    "basePath": "/api",
    "schemes": ["http", "https"],
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "securityDefinitions": {
        "session": {
            "type": "apiKey",
            "name": "session",
            "in": "cookie",
            "description": "Session-based authentication"
        }
    },
    "tags": [
        {
            "name": "Authentication",
            "description": "User authentication and session management"
        },
        {
            "name": "Cases",
            "description": "Patent case management operations"
        },
        {
            "name": "Profile",
            "description": "User profile management"
        },
        {
            "name": "Patents",
            "description": "Patent-related operations"
        },
        {
            "name": "Demo Requests",
            "description": "Demo request management"
        }
    ]
}

# Response models
def get_response_models():
    """Define common response models for Swagger documentation"""
    return {
        "SuccessResponse": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "example": True
                },
                "message": {
                    "type": "string",
                    "example": "Operation completed successfully"
                }
            }
        },
        "ErrorResponse": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "example": False
                },
                "message": {
                    "type": "string",
                    "example": "Error message"
                }
            }
        },
        "Case": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "example": "case_001"
                },
                "title": {
                    "type": "string",
                    "example": "AI-Powered Patent Analysis System"
                },
                "filing_date": {
                    "type": "string",
                    "format": "date",
                    "example": "2024-01-15"
                },
                "status": {
                    "type": "string",
                    "enum": ["Active", "Pending", "Completed", "Cancelled"],
                    "example": "Active"
                },
                "accepted_on": {
                    "type": "string",
                    "format": "date",
                    "example": "2024-02-01"
                },
                "accepted_by": {
                    "type": "string",
                    "example": "user_001"
                },
                "description": {
                    "type": "string",
                    "example": "A comprehensive system for analyzing patent documents using artificial intelligence"
                },
                "priority": {
                    "type": "string",
                    "enum": ["High", "Medium", "Low"],
                    "example": "High"
                },
                "assigned_to": {
                    "type": "string",
                    "example": "user_123"
                },
                "created_date": {
                    "type": "string",
                    "format": "date",
                    "example": "2024-01-15"
                },
                "due_date": {
                    "type": "string",
                    "format": "date",
                    "example": "2024-03-15"
                },
                "references": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "example": ["https://dummyurl.com/case_001/ref1", "https://dummyurl.com/case_001/ref2"]
                },
                "keywords": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "example": ["AI", "patent analysis", "document analysis"]
                }
            }
        },
        "UserProfile": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "example": "user_123"
                },
                "email": {
                    "type": "string",
                    "format": "email",
                    "example": "user@example.com"
                },
                "name": {
                    "type": "string",
                    "example": "John Doe"
                },
                "role": {
                    "type": "string",
                    "example": "Analyst"
                },
                "department": {
                    "type": "string",
                    "example": "Patent Analysis"
                }
            }
        },
        "Patent": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "example": "patent_001"
                },
                "title": {
                    "type": "string",
                    "example": "Machine Learning Patent Search System"
                },
                "patent_number": {
                    "type": "string",
                    "example": "US12345678"
                },
                "filing_date": {
                    "type": "string",
                    "format": "date",
                    "example": "2023-06-15"
                },
                "status": {
                    "type": "string",
                    "example": "Granted"
                },
                "inventors": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "example": ["John Smith", "Jane Doe"]
                },
                "abstract": {
                    "type": "string",
                    "example": "A system for searching patents using machine learning algorithms..."
                }
            }
        },
        "LoginRequest": {
            "type": "object",
            "required": ["email", "password"],
            "properties": {
                "email": {
                    "type": "string",
                    "format": "email",
                    "example": "user@example.com"
                },
                "password": {
                    "type": "string",
                    "example": "password123"
                }
            }
        },
        "PasswordChangeRequest": {
            "type": "object",
            "required": ["new_password"],
            "properties": {
                "new_password": {
                    "type": "string",
                    "example": "newpassword123"
                }
            }
        },
        "PasswordVerifyRequest": {
            "type": "object",
            "required": ["password"],
            "properties": {
                "password": {
                    "type": "string",
                    "example": "currentpassword123"
                }
            }
        },
        "CaseUpdateRequest": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["Active", "Pending", "Completed", "Cancelled"],
                    "example": "Completed"
                },
                "priority": {
                    "type": "string",
                    "enum": ["High", "Medium", "Low"],
                    "example": "High"
                },
                "assigned_to": {
                    "type": "string",
                    "example": "user_456"
                },
                "description": {
                    "type": "string",
                    "example": "Updated case description"
                }
            }
        },
        "DemoRequest": {
            "type": "object",
            "required": ["name", "email", "organization", "role", "date", "time", "timezone"],
            "properties": {
                "name": {
                    "type": "string",
                    "example": "John Doe",
                    "description": "Full name of the requester"
                },
                "email": {
                    "type": "string",
                    "format": "email",
                    "example": "john.doe@example.com",
                    "description": "Email address of the requester"
                },
                "organization": {
                    "type": "string",
                    "example": "Tech Corp",
                    "description": "Organization name"
                },
                "role": {
                    "type": "string",
                    "example": "Patent Attorney",
                    "description": "Role or title of the requester"
                },
                "date": {
                    "type": "string",
                    "format": "date",
                    "example": "2024-01-15",
                    "description": "Preferred date for the demo"
                },
                "time": {
                    "type": "string",
                    "format": "time",
                    "example": "14:30",
                    "description": "Preferred time for the demo"
                },
                "timezone": {
                    "type": "string",
                    "example": "UTC-5",
                    "description": "Time zone for the demo"
                }
            }
        },
        "DemoRequestResponse": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "example": True
                },
                "message": {
                    "type": "string",
                    "example": "Demo request submitted successfully"
                },
                "request_id": {
                    "type": "string",
                    "example": "demo_req_123",
                    "description": "Unique identifier for the demo request"
                }
            }
        }
    }

def initialize_swagger(app):
    """Initialize Swagger for the Flask app"""
    # Get response models and add them to the template
    response_models = get_response_models()
    swagger_template["definitions"] = response_models
    
    swagger = Swagger(app, config=swagger_config, template=swagger_template)
    return swagger

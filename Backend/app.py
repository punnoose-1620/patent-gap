import os
from flask_cors import CORS
from swagger import initialize_swagger
from flask import Flask, render_template, request, jsonify, redirect, url_for, session

from models.demo import *
from models.cases import *
from models.users import *
from models.alerts import *
from database import *
from controller import *
from env_controller import *
from data_processor import *
from llm_processor import *
from datetime import datetime
from sources.USPTO import *

app = Flask(__name__, 
            static_folder='../Assets',
            template_folder='../Frontend')
CORS(app)

# Set secret key for sessions
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Configuration
app.config['PORT'] = int(os.environ.get('PORT', 5000))
app.config['DEBUG'] = os.environ.get('DEBUG', 'True').lower() == 'true'

# Initialize Swagger
swagger = initialize_swagger(app)

# Routes for serving HTML pages
@app.route('/')
def index():
    """Serve the home page"""
    print('Collections: ', getCollectionsFromDatabase(connect_to_database()))
    if not checkCollectionExists(connect_to_database(), getCaseDatabaseName()):
        print('\nCreating cases collection: ', createCollection(connect_to_database(), getCaseDatabaseName()))
    if not checkCollectionExists(connect_to_database(), 'patents'):
        print('\nCreating patents collection: ', createCollection(connect_to_database(), 'patents'))
    if not checkCollectionExists(connect_to_database(), getUserDatabaseName()):
        print('\nCreating users collection: ', createCollection(connect_to_database(), getUserDatabaseName()))
    if not checkCollectionExists(connect_to_database(), getAlertDatabaseName()):
        print('\nCreating alerts collection: ', createCollection(connect_to_database(), getAlertDatabaseName()))
    if not checkCollectionExists(connect_to_database(), getDemoDatabaseName()):
        print('\nCreating demo_requests collection: ', createCollection(connect_to_database(), getDemoDatabaseName()))
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    """Serve the favicon.ico from the Assets directory"""
    print(f'Serving favicon-white.ico')
    return app.send_static_file('favicon-white.ico')

@app.route('/images/<path:imageName>')
def serve_image(imageName):
    """Serve images from the Assets directory"""
    return app.send_static_file(f'{imageName}')

@app.route('/login')
def login_page():
    """Serve the login page"""
    return render_template('login.html')

@app.route('/home')
def home_page():
    """Serve the home page after login"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    userData = get_user_profile(session['user_id'])
    if userData and userData.get('role') == 'client':
        return render_template('home-client.html')
    return render_template('home.html')

@app.route('/case-details')
def case_details_page():
    """Serve the case details page"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('case-details.html')

@app.route('/change-password')
def change_password_page():
    """Serve the change password page"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('change_password.html')

@app.route('/add-patent')
def add_patent_page():
    """Serve the add patent page"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('add-patent.html')

@app.route('/request-demo')
def request_demo_page():
    """Serve the request demo page"""
    return render_template('request-demo.html')


# API Endpoints
@app.route('/api/create-demo-request', methods=['POST'])
def create_demo_request():
    """
    Create a demo request
    ---
    tags:
      - Demo Requests
    summary: Create a new demo request
    description: Submit a request for a personalized demonstration of the patent management platform
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: demo_request
        description: Demo request information
        required: true
        schema:
          $ref: '#/definitions/DemoRequest'
    responses:
      200:
        description: Demo request created successfully
        schema:
          $ref: '#/definitions/DemoRequestResponse'
      400:
        description: Invalid input data
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        name = data.get('name')
        email = data.get('email')
        organization = data.get('organization')
        role = data.get('role')
        date = data.get('date')
        time = data.get('time')
        timezone = data.get('timezone')
        
        result = create_demo_request(name, email, organization, role, date, time, timezone)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating demo request: {str(e)}'
        }), 500

@app.route('/api/login', methods=['POST'])
def login():
    """
    Handle user login
    ---
    tags:
      - Authentication
    summary: Authenticate user and create session
    description: Validates user credentials and creates a session if successful
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: login_data
        description: User login credentials
        required: true
        schema:
          $ref: '#/definitions/LoginRequest'
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Login successful"
            redirect:
              type: string
              example: "/home"
      401:
        description: Invalid credentials
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        print(f'LOG: Login Request for {email}')
        
        result = login_user(email, password)
        
        if result['success']:
            session['user_id'] = result['user_id']
            session['email'] = email
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'redirect': '/home'
            })
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Login error: {str(e)}'
        }), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """
    Handle user logout
    ---
    tags:
      - Authentication
    summary: Logout user and clear session
    description: Clears the user session and logs them out
    produces:
      - application/json
    responses:
      200:
        description: Logout successful
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Logged out successfully"
            redirect:
              type: string
              example: "/"
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Logout')
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully',
        'redirect': '/'
    })

@app.route('/api/my-cases')
def my_cases():
    """
    Get user's cases
    ---
    tags:
      - Cases
    summary: Retrieve cases assigned to the current user
    description: Returns all cases assigned to the authenticated user
    produces:
      - application/json
    security:
      - session: []
    responses:
      200:
        description: Cases retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            cases:
              type: array
              items:
                $ref: '#/definitions/Case'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    user_id = session['user_id']
    print(f'LOG: {user_id} Get My Cases')
    try:
        print('User ID: ', user_id)
        cases = get_case_related_to_user(user_id)
        return jsonify({
            'success': True,
            'cases': cases
        })
    except Exception as e:
        print('Error fetching cases: ', str(e))
        return jsonify({
            'success': False,
            'message': f'Error fetching cases: {str(e)}'
        }), 500

@app.route('/api/open-cases')
def open_cases():
    """
    Get open cases
    ---
    tags:
      - Cases
    summary: Retrieve all open cases
    description: Returns all cases that are currently open (not completed or cancelled)
    produces:
      - application/json
    responses:
      200:
        description: Open cases retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            cases:
              type: array
              items:
                $ref: '#/definitions/Case'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Get Open Cases')
    try:
        cases = get_open_cases()
        return jsonify({
            'success': True,
            'cases': cases
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching open cases: {str(e)}'
        }), 500

@app.route('/api/profile')
def profile():
    """
    Get user profile
    ---
    tags:
      - Profile
    summary: Retrieve current user's profile information
    description: Returns the profile information for the authenticated user
    produces:
      - application/json
    security:
      - session: []
    responses:
      200:
        description: Profile retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            profile:
              $ref: '#/definitions/UserProfile'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    user_id = session['user_id']
    print(f'LOG: {user_id} Get Profile Data')
    try:
        profile_data = get_user_profile(user_id)
        return jsonify({
            'success': True,
            'profile': profile_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching profile: {str(e)}'
        }), 500

@app.route('/api/cases/<case_id>', methods=['GET'])
def get_case_details(case_id):
    """
    Get detailed information about a specific case
    ---
    tags:
      - Cases
    summary: Retrieve detailed information about a specific case
    description: Returns comprehensive details about a case by its ID
    produces:
      - application/json
    security:
      - session: []
    parameters:
      - name: case_id
        in: path
        type: string
        required: true
        description: The unique identifier of the case
        example: "case_001"
    responses:
      200:
        description: Case details retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            case:
              $ref: '#/definitions/Case'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      404:
        description: Case not found
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    print(f'LOG: {session["user_id"]} Get Case Details: {case_id}')
    try:
        case_data = get_case_by_id(case_id)
        if case_data:
            return jsonify({
                'success': True,
                'case': case_data
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Case not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching case details: {str(e)}'
        }), 500

@app.route('/api/cases/<case_id>', methods=['POST'])
def update_case_details(case_id):
    """
    Update details of a specific case
    ---
    tags:
      - Cases
    summary: Update case details
    description: Updates fields of a case (not just status)
    consumes:
      - application/json
    produces:
      - application/json
    security:
      - session: []
    parameters:
      - name: case_id
        in: path
        type: string
        required: true
        description: The unique identifier of the case
        example: "case_001"
      - in: body
        name: update_data
        description: Case detail update information
        required: true
        schema:
          $ref: '#/definitions/CaseUpdateRequest'
    responses:
      200:
        description: Case details updated successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Case details updated"
            updated_case:
              $ref: '#/definitions/Case'
      400:
        description: Invalid input data
        schema:
          $ref: '#/definitions/ErrorResponse'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      404:
        description: Case not found
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Update Case Details: {case_id}')
    try:
        update_data = request.get_json()
        if not update_data:
            return jsonify({'success': False, 'message': 'No update data provided'}), 400

        # Assume update_case is a function that updates the case and returns the updated case or None if not found
        result = update_case(case_id, update_data)
        if result.get('success'):
            updated_case = get_case_by_id(case_id)
            return jsonify({
                'success': True,
                'message': 'Case details updated',
                'updated_case': updated_case
            })
        else:
            return jsonify({'success': False, 'message': 'Case not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating case details: {str(e)}'}), 500

@app.route('/api/cases/<case_id>/update-status', methods=['POST'])
def update_case_status(case_id):
    """
    Update the status of a specific case
    ---
    tags:
      - Cases
    summary: Update case information
    description: Updates various fields of a case including status, priority, assignment, etc.
    consumes:
      - application/json
    produces:
      - application/json
    security:
      - session: []
    parameters:
      - name: case_id
        in: path
        type: string
        required: true
        description: The unique identifier of the case
        example: "case_001"
      - in: body
        name: update_data
        description: Case update information
        required: true
        schema:
          $ref: '#/definitions/CaseUpdateRequest'
    responses:
      200:
        description: Case updated successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Status updated"
            updated_case:
              $ref: '#/definitions/Case'
      400:
        description: Invalid input data
        schema:
          $ref: '#/definitions/ErrorResponse'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      404:
        description: Case not found
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Update Case Status: {case_id}')
    try:
        update_data = request.get_json()
        if not update_data or not isinstance(update_data, dict):
            return jsonify({'success': False, 'message': 'Invalid input data'}), 400

        result = update_case(case_id, update_data)
        if result.get('success'):
            updated_case = get_case_by_id(case_id)
            return jsonify({'success': True, 'message': result.get('message', 'Status updated'), 'updated_case': updated_case})
        else:
            return jsonify({'success': False, 'message': result.get('message', 'Failed to update status')}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating case status: {str(e)}'}), 500

@app.route('/api/cases/<case_id>/patents')
def get_case_patents(case_id):
    """
    Get related patents for a specific case
    ---
    tags:
      - Patents
    summary: Retrieve patents related to a specific case
    description: Returns all patents that are related to the specified case
    produces:
      - application/json
    security:
      - session: []
    parameters:
      - name: case_id
        in: path
        type: string
        required: true
        description: The unique identifier of the case
        example: "case_001"
    responses:
      200:
        description: Related patents retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            patents:
              type: array
              items:
                $ref: '#/definitions/Patent'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Get Case Patents: {case_id}')
    try:
        patents = get_case_related_patents(case_id)
        return jsonify({
            'success': True,
            'patents': patents
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching related patents: {str(e)}'
        }), 500

@app.route('/api/verify-password', methods=['POST'])
def api_verify_password():
    """
    Verify if the entered password matches the user's current password
    ---
    tags:
      - Profile
    summary: Verify current password
    description: Validates if the provided password matches the user's current password
    consumes:
      - application/json
    produces:
      - application/json
    security:
      - session: []
    parameters:
      - in: body
        name: password_data
        description: Password to verify
        required: true
        schema:
          $ref: '#/definitions/PasswordVerifyRequest'
    responses:
      200:
        description: Password verification result
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            valid:
              type: boolean
              example: true
      400:
        description: Password is required
        schema:
          $ref: '#/definitions/ErrorResponse'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Verify User Password')
    try:
        data = request.get_json()
        entered_password = data.get('password')
        user_id = session['user_id']

        if entered_password is None:
            return jsonify({'success': False, 'message': 'Password is required'}), 400

        is_valid = verify_password(user_id, entered_password)
        return jsonify({'success': True, 'valid': is_valid})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error verifying password: {str(e)}'}), 500

@app.route('/api/change-password', methods=['POST'])
def api_change_password():
    """
    Change the user's password
    ---
    tags:
      - Profile
    summary: Change user password
    description: Updates the authenticated user's password
    consumes:
      - application/json
    produces:
      - application/json
    security:
      - session: []
    parameters:
      - in: body
        name: password_data
        description: New password information
        required: true
        schema:
          $ref: '#/definitions/PasswordChangeRequest'
    responses:
      200:
        description: Password changed successfully
        schema:
          $ref: '#/definitions/SuccessResponse'
      400:
        description: Invalid input or password requirements not met
        schema:
          $ref: '#/definitions/ErrorResponse'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Change User Password')
    try:
        data = request.get_json()
        new_password = data.get('new_password')

        if not new_password:
            return jsonify({'success': False, 'message': 'New password is required'}), 400

        user_id = session['user_id']
        result = change_password(user_id, new_password)
        if result.get('success'):
            return jsonify({'success': True, 'message': result.get('message')})
        else:
            return jsonify({'success': False, 'message': result.get('message')}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error changing password: {str(e)}'}), 500
  
@app.route('/api/add-patent', methods=['POST'])
def add_patent():
    """
    Add a new patent
    ---
    tags:
      - Patents
    summary: Add a new patent
    description: Adds a new patent to the database
    consumes:
      - application/json
    produces:
      - application/json
    security:
      - session: []
    parameters:
      - in: body
        name: patent_data
        description: Patent information
        required: true
        schema:
          $ref: '#/definitions/Patent'
    responses:
      200:
        description: Patent added successfully
        schema:
          $ref: '#/definitions/PatentResponse'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Add New Patent: {request.get_json()}')
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        result = create_patent(data)
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error adding patent: {str(e)}'}), 500

@app.route('/api/upload-file-to-local-storage/<case_id>', methods=['POST'])
def upload_file_to_local_storage(case_id):
    """
    Upload a file to local storage and return its URL
    ---
    tags:
      - Files
    summary: Upload file to local storage
    description: Saves the uploaded file to 'documentFiles' folder and returns its URL
    consumes:
      - multipart/form-data
    produces:
      - application/json
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: The file to upload
    responses:
      200:
        description: File uploaded successfully
    """

    from werkzeug.utils import secure_filename

    # Check authentication
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Upload File to Local Storage')
    # Check file in request
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part in the request'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400

    try:
        # Safe filename
        filename = secure_filename(file.filename)
        # Ensure documentFiles directory exists
        upload_folder = os.path.join(os.getcwd(), 'documentFiles')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Construct file URL (relative)
        file_url = f'/documentFiles/{filename}'

        case_data = get_case_by_id(case_id)
        if case_data is not None:
          documents = case_data.get('documents', [])
          if not isinstance(documents, list):
            documents = []
          documents.append({
            'url': file_url,
            'source': 'local'
          })
          case_data['documents'] = documents
          from database import connect_to_database
          db = connect_to_database()
          updateDataById(db, collectionName=getCaseDatabaseName(), entryData={'_id': case_id, 'documents': documents})

        # Optionally: Here you might want to update the corresponding case to add this file URL

        return jsonify({'success': True, 'message': 'File uploaded successfully', 'file_url': file_url}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to upload file: {str(e)}'}), 500

@app.route('/api/upload-file/<case_id>', methods=['POST'])
def upload_file(case_id):
    """
    Upload a file
    ---
    tags:
      - Files
    summary: Upload a file
    description: Uploads a file to the database
    consumes:
      - application/json
    produces:
      - application/json
    security:
      - session: []
    parameters:
      - in: body
        name: file
        description: The file to upload
        required: true
        schema:
          type: string
          format: binary
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Upload File: {case_id}')

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    # Use uploadToGcpBucket from database.py to upload the file
    # Expecting data to have: 'bucketName', 'sourceFile', 'destinationBlob'
    bucket_name = data.get('bucketName')
    source_file = data.get('sourceFile')
    destination_blob = data.get('destinationBlob')

    result = {}

    if not all([bucket_name, source_file, destination_blob]):
        result = {'success': False, 'message': 'Missing required file upload parameters'}
    else:
        #TODO: Update File's url to case entry using case_id
        case_data = get_case_by_id(case_id)
        upload_url = uploadToGcpBucket(bucket_name, source_file, destination_blob)
        if upload_url is not None:
            # Add upload_url to the references list in case_data
            if case_data is not None:
                references = case_data.get('references', [])
                if not isinstance(references, list):
                    references = []
                references.append({
                  'url': upload_url,
                  'source': 'local'
                  })
                case_data['documents'] = references
                # Update the case entry in the database
                from database import connect_to_database
                db = connect_to_database()
                updateDataById(db, collectionName=getCaseDatabaseName(), entryData={'_id': case_id, 'documents': references})
            result = {
                'success': True,
                'message': 'File uploaded successfully',
                'bucket': bucket_name,
                'blob': destination_blob
            }
        else:
            result = {
                'success': False,
                'message': 'File upload failed'
            }
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route('/api/alerts', methods=['GET'])
def get_all_alerts():
    """
    Get all alerts
    ---
    tags:
      - Alerts
    summary: Get all alerts
    description: Returns all alerts
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {session["user_id"]} Get All Alerts')

    try:
        alerts = get_alerts()
        return jsonify({
            'success': True,
            'alerts': alerts
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting all alerts: {str(e)}'}), 500

@app.route('/api/alerts/', methods=['GET'])
def get_user_alerts():
    """
    Get all alerts related to a specific user
    ---
    tags:
      - Alerts
    summary: Get all alerts related to a specific user
    description: Returns all alerts related to the specified user
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    user_id = session['user_id']
    print(f'LOG: {session["user_id"]} Get User Alerts')
    try:
        user_alerts = get_alerts_for_user(user_id)
        return jsonify({
            'success': True,
            'alerts': user_alerts
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting all alerts: {str(e)}'}), 500

@app.route('/api/trigger-similarity-analysis', methods=['POST'])
def trigger_similarity_analysis():
  """
  Trigger a similarity analysis for a specific case.

  ---
  tags:
    - Similarity Analysis
  summary: Run similarity analysis for a specific case
  description: 
    Triggers a keyword-based similarity analysis for a given case. If no keywords are provided in the request, it will attempt to use the keywords from the case itself. 
    Retrieves similar USPTO documents and references using the keywords, generates and updates reports for the case, and creates an alert for the triggering user.
  
  Request Body:
    - case_id (str): The unique identifier of the case.
    - keywords (list, optional): A list of keywords to use for the similarity analysis. If omitted or empty, attempts to extract from the given case.

  Responses:
    200:
      description: Similarity analysis completed and alert created successfully.
    400:
      description: Bad request, such as missing user ID, data, or keywords.
    500:
      description: Internal server error during similarity analysis.
  """
  if 'user_id' not in session:
      return jsonify({'success': False, 'message': 'User ID is not in session'}), 400
  user_id = session['user_id']
  print(f'LOG: {session["user_id"]} Trigger Similarity Analysis')
  try:
    data = request.get_json()
    print('TEST: trigger_similarity_analysis data: ', json.dumps(data, indent=4))
    if data is None:
      return jsonify({'success': False, 'message': 'No data provided'}), 400
    case_id = data.get('case_id', None)
    keywords = data.get('keywords', [])

    if (case_id is None) or (case_id == ''):
      return jsonify({'success': False, 'message': 'Case ID is required'}), 400
    if keywords is None:
      return jsonify({'success': False, 'message': 'Keywords are required'}), 400
      
    # Try to get keywords from local case data if not provided
    if (keywords is None) or (len(keywords) == 0):
      print('No keywords provided')
      case_data = get_case_by_id(case_id)
      if case_data is not None:
        keywords_from_case = case_data.get('keywords', [])
        if (keywords_from_case is None) or (len(keywords_from_case) == 0):
          return jsonify({'success': False, 'message': 'No keywords provided'}), 400
        keywords = keywords_from_case
    # Get similar documents from USPTO
    similarUsptoDocuments = getKeywordDocumentsUSPTO(keywords, load_to_database=False)    # Similar documents normalized, processed and with references & embeddings
    print('similarUsptoDocuments sample: ', json.dumps(similarUsptoDocuments[0], indent=4))
    if (similarUsptoDocuments is None) or (len(similarUsptoDocuments) == 0):
      return jsonify({'success': False, 'message': 'No similar documents found'}), 400
    # Get references as normalized list from similar documents
    references = getReferenceFromNormalizedList(similarUsptoDocuments, case_id)
    print('References calculated')
    if (references is None) or (len(references) == 0):
      return jsonify({'success': False, 'message': 'No references found'}), 400
    # Generate reports for the case
    fullReport, summaryReport = generateReports(case_id)
    case_data = get_case_by_id(case_id)
    case_data['report'] = fullReport
    case_data['summary'] = summaryReport
    update_case(case_id, case_data)
    
    newAlertId = create_alert(user_id, case_id, references)
    add_to_alerts(
        triggered_by=user_id, 
        triggered_at=datetime.datetime.utcnow().isoformat(), 
        alert_users=[user_id], 
        title='HETEROJUNCTION BIPOLAR TRANSISTOR', 
        description='Patent Expired Due to NonPayment of Maintenance Fees Under 37 CFR 1.362')
    print('New Alert ID:', newAlertId)
    return jsonify({'success': True, 'message': 'Similarity analysis completed', 'alert_id': newAlertId}), 200
  except Exception as e:
    print(f'Error triggering similarity analysis: {str(e)}')
    return jsonify({'success': False, 'message': f'Error triggering similarity analysis: {str(e)}'}), 500

@app.route('/api/case-keywords', methods=['GET'])
def get_case_keywords():
  headers = None
  data = request.get_json()
  document_url = data.get('document_url')
  title = data.get('title')
  description = data.get('description')
  source = data.get('source')
  if source == 'uspto':
    headers = {"X-API-KEY": getEnvKey('uspto')}
  content = None
  if document_url is not None:
    content = readDocumentFromUrl(document_url, headers=headers)
    if title is not None:
      content = title + '. ' + content + '.'
    if description is not None:
      content = content + '. ' + description + '.'
  elif title is not None and description is not None:
    content = title + '. ' + description + '.'
  else:
    return jsonify({'success': False, 'message': 'No document URL or title/description provided'}), 400
  
  if content is None:
    return jsonify({'success': False, 'message': 'Failed to read document'}), 400
  else:
    keywords = getKeywordsFromContent(content)
    if (keywords is None) or len(keywords) == 0:
      return jsonify({'success': False, 'message': 'No keywords found. The document may be empty or might contain only stop words.'}), 400
    return jsonify({'success': True, 'keywords': keywords})

@app.route('/api/import-patent-from-uspto', methods=['POST'])
def api_import_patent_from_uspto():
  """
  Import a patent from the US Patent Office and create a case
  """
  if 'user_id' not in session:
    print('\nUser ID is not in session')
    return jsonify({'success': False, 'message': 'User ID is not in session'}), 400
  user_id = session['user_id']
  print(f'LOG: {session["user_id"]} Import Patent from USPTO')
  data = request.get_json()
  if data is None:
    print('\nNo Data provided')
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  if 'patentId' not in data.keys():
    print('\nPatent ID is not Provided')
    return jsonify({'success': False, 'message': 'Patent ID is not provided'}), 400
  patent_id = data.get('patentId')
  if patent_id is None or patent_id == '':
    print('\nPatent ID is not valid')
    return jsonify({'success': False, 'message': 'Patent ID is not valid'}), 400
  
  try:
    uspto_instance = USPTOPatentAPI(api_key=getEnvKey('uspto'))
    uspto_data = uspto_instance.get_complete_patent_info(patent_id)
    uspto_data['created_by'] = user_id
    uspto_data['keywords'] = getKeywordsFromPatent(uspto_data['documents'])
    # TODO: Get Keywords from USPTO Data
    print(f'\nUSPTO Data: {json.dumps(uspto_data, indent=4)}')
    if uspto_data is None:
      return jsonify({'success': False, 'message': 'Failed to fetch patent from USPTO. Please check the patent ID and try again.'}), 400
    # creationResult = create_case(uspto_data)
    return jsonify({
      'success': True, 
      'message': 'Patent data imported successfully', 
      'case_id': f"uspto_{patent_id}",
      'keywords': uspto_data['keywords']
      }), 200
  except Exception as e:
    print(f'\nError getting patent data from USPTO: {str(e)}')
    if 'Rate limit exceeded' in str(e):
      populateDummyData(patent_id, user_id)
    return jsonify({'success': False, 'message': f'Error getting patent data from USPTO: {str(e)}'}), 500

@app.route('/api/create-patent', methods=['POST'])
def api_create_patent():
  if 'user_id' not in session:
    return jsonify({'success': False, 'message': 'User ID is not in session'}), 400
  if session['user_id'] is None:
    return jsonify({'success': False, 'message': 'User ID is required'}), 400
  user_id = session['user_id']
  print(f'LOG: {session["user_id"]} Create Patent')
  try:
    data = request.get_json()
    print(f'Create Patent Data by {user_id}: {json.dumps(data, indent=4)}')
    # patent_data = data.get('patent_data')
    data['created_by'] = user_id
    data['created_date'] = datetime.now().strftime('%Y-%m-%d')
    created_patent = create_patent(data)
    print('\nCreated Patent: ', created_patent, '\n')
    returnVal = {
      'success': True, 
      'message': 'Patent created successfully', 
      'case_id': created_patent['patent_id']
      }
    return jsonify(returnVal), 200
  except Exception as e:
    print(f'Error creating patent: {str(e)}')
    return jsonify({'success': False, 'message': f'Error creating patent: {str(e)}'}), 500

@app.route('/api/fetch-patent-from-uspto', methods=['POST'])
def fetch_patent_from_uspto():
  """
  Fetch a patent from the US Patent Office and create a case
  ---
  tags:
    - Patents
  summary: Fetch patent from USPTO
  description: |
    Fetches patent data from the US Patent and Trademark Office (USPTO) using the provided patent ID.
    The patent data is then normalized and automatically created as a case in the system.
    The case will be monitored for similarity analysis.
  consumes:
    - application/json
  produces:
    - application/json
  security:
    - session: []
  parameters:
    - in: body
      name: patent_request
      description: Patent ID to fetch from USPTO
      required: true
      schema:
        type: object
        required:
          - patentId
        properties:
          patentId:
            type: string
            description: The USPTO patent number/ID to fetch
            example: "US12345678"
  responses:
    200:
      description: Patent fetched successfully and case created
      schema:
        type: object
        properties:
          success:
            type: boolean
            example: true
          message:
            type: string
            example: "Patent has been fetched successfully. This case is now being monitored for similarity."
          case_id:
            type: string
            description: The ID of the created case
            example: "case_12345"
    400:
      description: Bad request - missing or invalid patent ID, or failed to fetch/normalize patent data
      schema:
        type: object
        properties:
          success:
            type: boolean
            example: false
          message:
            type: string
            example: "Patent ID is required"
    500:
      description: Internal server error during patent data processing
      schema:
        type: object
        properties:
          success:
            type: boolean
            example: false
          message:
            type: string
            example: "Error normalizing patent data: [error details]"
  """
  if 'user_id' not in session:
    return jsonify({'success': False, 'message': 'User ID is not in session'}), 400
  print(f'LOG: {session["user_id"]} Fetch Patent from USPTO')
  data = request.get_json()
  if data is None:
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  if 'patentId' not in data:
    return jsonify({'success': False, 'message': 'Patent ID is required'}), 400
  
  patentId = data.get('patentId')
  print('Patent ID: ', patentId)
  if patentId is None or patentId.trim() == '':
    return jsonify({'success': False, 'message': 'Patent ID is required'}), 400

  try: 
    uspto_api = USPTOPatentAPI(api_key=getEnvKey('uspto'))
    patentData = uspto_api.get_complete_patent_info(patentId)     # Document data already included. Only references are missing.
    if (patentData is None) or ('_id' not in str(patentData)) or (patentData['_id'] is None) or (patentData['_id'] == ''):
      print('Patent Data is None or _id is not in keys or _id is None or _id is empty')
      return jsonify({'success': False, 'message': 'Failed to fetch patent from USPTO. Please check the patent ID and try again.'}), 400

    creationResult = create_case(patentData)
    if 'case_id' not in creationResult:
      return jsonify({'success': False, 'message': 'Failed to create case. Please check the patent data and try again.'}), 400
      
    return jsonify({
      'success': True, 
      'message': 'Patent has been fetched successfully. This case is now being monitored for similarity.', 
      'case_id': creationResult['case_id'],
      'keywords': patentData['keywords']
      }), 200

  except Exception as e:
    print(f'Error normalizing patent data: {str(e)}')
    return jsonify({'success': False, 'message': f'Error normalizing patent data: {str(e)}'}), 500

if __name__ == '__main__':
    port = app.config['PORT']
    debug = app.config['DEBUG']
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

import os
import io
import requests
import threading
import pandas as pd
from flask_cors import CORS
from datetime import datetime as dt
from swagger import initialize_swagger
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response, stream_with_context

from models.demo import *
from models.cases import *
from models.users import *
from models.alerts import *
from models.documents import *
from models.infringements import *
from models.search_history import *
from models.infringements import (
    get_infringement_by_id as _model_get_infringement_by_id,
    get_infringements_by_ids as _model_get_infringements_by_ids,
    get_infringements_by_created_date as _model_get_infringements_by_created_date,
    get_infringements_by_parent_case_id as _model_get_infringements_by_parent_case_id,
    update_infringement_by_id as _model_update_infringement_by_id,
    delete_infringement_by_id as _model_delete_infringement_by_id,
)

from sources.USPTO import *
from sources.Gemini import *
from sources.OpenAlex import *
from sources.Sources import *

from database import *
from controller import *
from llm_processor import *
from data_processor import *
from env_controller import *
from live_search.liveSearchController import *
from file_controller import *


app = Flask(__name__, 
            static_folder='../Assets',
            template_folder='../Frontend')
CORS(app, origins="*")

# Set secret key for sessions
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Configuration
app.config['PORT'] = int(os.environ.get('PORT', 5000))
app.config['DEBUG'] = os.environ.get('DEBUG', 'True').lower() == 'true'
app.config['ENVIRONMENT'] = os.environ.get('ENVIRONMENT', 'dev')

# Initialize Swagger
swagger = initialize_swagger(app)

# Helper function to generate chunks of data
def chunk_generator(data, chunk_size=8192):    
  for i in range(0, len(data), chunk_size):        
    yield data[i:i + chunk_size]

# Helper function to get user_id from header or session
def get_user_id():
    """
    Get user_id from X-User-ID header or session.
    Returns None if not found.
    """
    # First check header
    user_id = request.headers.get('X-User-ID')
    if user_id:
        return user_id
    
    # Fallback to session for backward compatibility
    if 'user_id' in session:
        return session['user_id']
    
    return None

# Routes for serving HTML pages
@app.route('/')
def index():
    """Serve the home page"""
    # try:
    #   print('Collections: ', getCollectionsFromDatabase(connect_to_database()))
    #   if not checkCollectionExists(connect_to_database(), getCaseDatabaseName()):
    #       print('\nCreating cases collection: ', createCollection(connect_to_database(), getCaseDatabaseName()))
    #   if not checkCollectionExists(connect_to_database(), 'patents'):
    #       print('\nCreating patents collection: ', createCollection(connect_to_database(), 'patents'))
    #   if not checkCollectionExists(connect_to_database(), getUserDatabaseName()):
    #       print('\nCreating users collection: ', createCollection(connect_to_database(), getUserDatabaseName()))
    #   if not checkCollectionExists(connect_to_database(), getAlertDatabaseName()):
    #       print('\nCreating alerts collection: ', createCollection(connect_to_database(), getAlertDatabaseName()))
    #   if not checkCollectionExists(connect_to_database(), getDemoDatabaseName()):
    #       print('\nCreating demo_requests collection: ', createCollection(connect_to_database(), getDemoDatabaseName()))
    # except Exception as e:
    #   print('\nERROR: Error creating collections: ', str(e))
    return render_template('index-new.html')

@app.route('/favicon.ico')
def favicon():
    """Serve the favicon.ico from the Assets directory"""
    print(f'Serving favicon-white.ico')
    return app.send_static_file('favicon-white.ico')

@app.route('/images/<path:imageName>')
def serve_image(imageName):
    """Serve images from the Assets directory"""
    return app.send_static_file(f'{imageName}')

## Front End Pages

@app.route('/login')
def login_page():
    """Serve the login page"""
    # if 'user_id' in session:
    #     return redirect(url_for('home_page'))
    return render_template('login-new.html')

@app.route('/home')
def home_page():
    """Serve the home page after login"""
    # if 'user_id' not in session:
    #     return redirect(url_for('login_page'))
    # userData = get_user_profile(session['user_id'])
    return render_template('home-new.html')

@app.route('/case-details')
def case_details_page():
    """Serve the case details page"""
    # if 'user_id' not in session:
    #     return redirect(url_for('login_page'))
    return render_template('case-details-new.html')

@app.route('/change-password')
def change_password_page():
    """Serve the change password page"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login_page'))
    return render_template('change_password.html')

@app.route('/add-patent')
def add_patent_page():
    """Serve the add patent page"""
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for('login_page'))
    return render_template('add-patent.html')

@app.route('/request-demo')
def request_demo_page():
    """Serve the request demo page"""
    return render_template('request-demo-new.html')
    return render_template('request-demo.html')

@app.route('/show-demo')
def show_demo_page():
  """Serve the show demo page"""
  return render_template('show-demo.html')

@app.route('/popups/<popupName>')
def show_popup(popupName):
  """Serve the popup page"""
  return render_template(f'popups/{popupName}.html')

@app.route('/analysis-page')
def analysis_page():
  """Serve the analysis page"""
  return render_template('analysis-results.html');

@app.route('/infringement-details')
def infringement_details_page():
  """Serve the infringement details page"""
  return render_template('infringement.html');


# API Endpoints
@app.route('/api/source-stats')
def get_source_stats():
  sources = Sources()
  """Get source stats"""
  return jsonify({
    'success': True,
    'source_stats': {
      'remaining_sources': len(sources.getRemainingSources()),
      'integrated_sources': len(sources.getIntegratedSourceTitles()),
      'covered_jurisdictions': len(sources.getCoveredJurisdictions())
    }
  })

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
        print('LOG: Login result:', result)
        
        if result['success']:
            session['user_id'] = result['user_id']
            session['email'] = email
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'redirect': '/home',
                'user_id': result['user_id']
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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Logout')
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully',
        'redirect': '/'
    })

@app.route('/api/stats')
def get_case_stats():
  user_id = get_user_id()
  returnStats = {
    'activeScans': 0,
    'patentsAnalyzed': 0,
    'highRiskMatches': 0,
    'mediumRiskMatches': 0,
    'lowRiskMatches': 0,
    'clearedPatents': 0
  }
  if not user_id:
    print('TEST: My Cases - Not authenticated')
    return jsonify({'success': False, 'message': 'Not authenticated'}), 401
  try:
    cases = get_case_related_to_user(user_id)
    for case in cases:
      # Calculate Risk Counts
      infringement_percentage = calculate_average_infringement_percentage(case)
      risk_level = get_risk_level(infringement_percentage)
      if risk_level == 'high':
        returnStats['highRiskMatches'] += 1
      elif risk_level == 'medium':
        returnStats['mediumRiskMatches'] += 1
      else:
        returnStats['lowRiskMatches'] += 1
      # Calculate Active Count
      if case.get('current_status', '').strip().lower() == 'processing':
        returnStats['activeScans'] += 1
      # Calculate Analyzed Count
      similar_claims = case.get('similar_claims', [])
      infringement_analysis_flag = case.get('infringement_analysis_flag', '').strip().lower()
      infringements = case.get('infringements', [])
      if ('complete' in infringement_analysis_flag and len(similar_claims) > 0) or (len(infringements) > 0):
        returnStats['patentsAnalyzed'] += 1
      # Calculate Cleared Count
      if (len(infringements) == 0) or ((len(similar_claims) == 0) and ('complete' not in infringement_analysis_flag)):
        returnStats['clearedPatents'] += 1
    return returnStats
  except Exception as e:
    print(f'Error getting case stats: {str(e)}')
    return jsonify({'success': False, 'message': f'Error getting case stats: {str(e)}'}), 500

@app.route('/api/all-cases')
def all_cases():
    # if 'user_id' not in session:
    #     print('TEST: My Cases - Not authenticated')
    #     return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    # user_id = session['user_id']
    # print(f'LOG: {user_id} Get My Cases')
    page = request.args.get('page', 1, type=int)
    try:
        results = get_all_cases(page=page, paginated=True)
        cases = results.get('items', [])
        ids = [case.get('_id') for case in cases]
        print(f'LOG: All Cases({len(cases)}): {ids}')
        return jsonify({
            'success': True,
            'items': cases,
            'pagination': results.get('pagination', {})
        })
    except Exception as e:
        print('Error fetching cases: ', str(e))
        return jsonify({
            'success': False,
            'message': f'Error fetching cases: {str(e)}'
        }), 500

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
    user_id = get_user_id()
    if not user_id:
      print('TEST: My Cases - Not authenticated')
      return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Get My Cases')
    page = request.args.get('page', 1, type=int)
    try:
        print('User ID: ', user_id)
        results = get_case_related_to_user(user_id, page=page, paginated=True)
        return jsonify({
            'success': True,
            'items': results.get('items', []),
            'pagination': results.get('pagination', {})
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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Get Open Cases')
    page = request.args.get('page', 1, type=int)
    try:
        results = get_open_cases(page=page, paginated=True)
        return jsonify({
            'success': True,
            'items': results.get('items', []),
            'pagination': results.get('pagination', {})
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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    print(f'LOG: {user_id} Get Profile Data')
    try:
        profile_data = get_user_profile(user_id)
        print(f'LOG: Profile Data {user_id}: {json.dumps(profile_data, indent=4)}')
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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    print(f'LOG: {user_id} Get Case Details: {case_id}')
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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Update Case Details: {case_id}')
    try:
        update_data = request.get_json()
        if not update_data:
            return jsonify({'success': False, 'message': 'No update data provided'}), 400

        # Assume update_case is a function that updates the case and returns the updated case or None if not found
        update_data['last_updated'] = dt.now()
        result = update_case(case_id, update_data)
        if result.get('success'):
            updated_case = get_case_by_id(case_id)
            print('\nLOG: Case updated for update_case(', case_id, '): ', updated_case)
            return jsonify({
                'success': True,
                'message': 'Case details updated',
                'updated_case': updated_case
            })
        else:
            print('\nERROR: Case not found for update_case: ', case_id)
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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Update Case Status: {case_id}')
    try:
        update_data = request.get_json()
        if not update_data or not isinstance(update_data, dict):
            return jsonify({'success': False, 'message': 'Invalid input data'}), 400

        update_data['last_updated'] = dt.now()
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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Get Case Patents: {case_id}')
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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Verify User Password')
    try:
        data = request.get_json()
        entered_password = data.get('password')

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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Change User Password')
    try:
        data = request.get_json()
        new_password = data.get('new_password')

        if not new_password:
            return jsonify({'success': False, 'message': 'New password is required'}), 400

        result = change_password(user_id, new_password)
        if result.get('success'):
            return jsonify({'success': True, 'message': result.get('message')})
        else:
            return jsonify({'success': False, 'message': result.get('message')}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error changing password: {str(e)}'}), 500
  
# Create User
@app.route('/api/create-attorney', methods=['POST'])
def api_create_attorney():
  try:
    data = request.get_json()
    if not data:
      return jsonify({'success': False, 'message': 'No data provided'}), 400
    if not data.get('email'):
      return jsonify({'success': False, 'message': 'Email is required'}), 400
    if not data.get('password'):
      return jsonify({'success': False, 'message': 'Password is required'}), 400
    if not data.get('full_name'):
      return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    data['created_date'] = dt.now().strftime('%Y-%m-%d')
    data['role'] = 'attorney'

    if does_user_exist(data.get('email')):
      return jsonify({'success': False, 'message': 'Email already in use'}), 400

    print(f'Create Attorney Data: {json.dumps(data, indent=4)}')
    return jsonify(create_user(data))
  except Exception as e:
    return jsonify({
      'success': False, 
      'message': f'Error creating attorney: {str(e)}'
      }), 500

@app.route('/api/update-attorney', methods=['POST'])
def api_update_attorney():
  """
  Update an attorney's information
  ---
  tags:
    - Attorneys
  summary: Update attorney information
  description: Updates the information of an attorney
  consumes:
    - application/json
  produces:
    - application/json
  security:
    - session: []
  parameters:
    - in: body
      name: attorney_data
      description: Attorney information
      required: true
    responses:
      200:
        description: Attorney updated successfully
    returns structure:
      {
        'success': True,
        'message': 'User updated successfully',
        'user_id': 'user_id'
      }
  """
  try:
    data = request.get_json()
    if not data:
      return jsonify({'success': False, 'message': 'No data provided'}), 400
    if not data.get('_id'):
      return jsonify({'success': False, 'message': 'Attorney ID is required'}), 400
    if not data.get('email'):
      return jsonify({'success': False, 'message': 'Email is required'}), 400
    if not data.get('full_name'):
      return jsonify({'success': False, 'message': 'Name is required'}), 400

    user_id = get_user_id()
    if not user_id:
      return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    data['updated_date'] = dt.now().strftime('%Y-%m-%d')
    data['role'] = 'attorney'

    existing_user = get_user_profile(user_id, show_password=True)
    if not existing_user:
      return jsonify({'success': False, 'message': 'Attorney not found'}), 404

    return jsonify(update_user(data, user_id))
  except Exception as e:
    return jsonify({'success': False, 'message': f'Error updating attorney: {str(e)}'}), 500

@app.route('/api/update-password', methods=['POST'])
def api_update_password():
  try:
    print(f'LOG: Update Password Request Initiated')
    data = request.get_json()
    print(f'LOG: Update Password Data: {json.dumps(data, indent=4)}')
    if not data:
      return jsonify({'success': False, 'message': 'No data provided'}), 400
    if not data.get('password'):
      return jsonify({'success': False, 'message': 'Password is required'}), 400
    if data.get('password') == 'null':
      return jsonify({'success': False, 'message': 'Password is invalid/null'}), 400
    if not data.get('old_password'):
      return jsonify({'success': False, 'message': 'Old Password is required'}), 400
    if data.get('old_password') == 'null':
      return jsonify({'success': False, 'message': 'Old Password is invalid/null'}), 400
    if not data.get('user_id'):
      return jsonify({'success': False, 'message': 'User ID is required'}), 400

    verified = verify_password(data.get('user_id'), data.get('old_password'))
    if verified is True:
      result = change_password(data.get('user_id'), data.get('password'))
      if result.get('success'):
        return jsonify({'success': True, 'message': result.get('message')})
      else:
        return jsonify({'success': False, 'message': result.get('message')}), 400
    else:
      return jsonify({'success': False, 'message': 'Invalid password'}), 400

  except Exception as e:
    return jsonify({'success': False, 'message': f'Error verifying password: {str(e)}'}), 500

@app.route('/api/add-patent', methods=['POST'])
def add_patent():
    """
    Add a new patent (legacy endpoint)
    ---
    tags:
      - Patents
    summary: Add a new patent (deprecated)
    description: |
      Legacy endpoint for adding patents. Consider using /api/create-patent instead.
      Adds a new patent to the database.
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
          $ref: '#/definitions/PatentCreateRequest'
    responses:
      200:
        description: Patent added successfully
        schema:
          $ref: '#/definitions/PatentResponse'
      400:
        description: Bad request - invalid data
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
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Add New Patent: {request.get_json()}')
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        data['created_by'] = user_id
        data['created_date'] = dt.now().strftime('%Y-%m-%d')
        current_id = data.get('_id')
        if current_id is None:
          data['_id'] = f"local_{str(uuid.uuid4())[:8]}"
        if 'local_' not in current_id:
          data['_id'] = f"local_{current_id}"
        result = create_patent(data)
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error adding patent: {str(e)}'}), 500

@app.route('/api/update-patent', methods=['POST'])
def update_patent():
  try:
    data = request.get_json()
    if not data:
      return jsonify({'success': False, 'message': 'No data provided'}), 400
    if not data.get('_id'):
      return jsonify({'success': False, 'message': 'Patent ID is required'}), 400
    
    data['last_updated'] = dt.now()
    return jsonify(update_case(data.get('_id'), data))
  except Exception as e:
    return jsonify({'success': False, 'message': f'Error updating patent: {str(e)}'}), 500

@app.route('/api/upload-file-to-local-storage/<case_id>', methods=['POST'])
def upload_file_to_local_storage(case_id):
    """
    Upload a file to local storage and return its URL
    ---
    tags:
      - Files
    summary: Upload file to local storage
    description: |
      Saves the uploaded file to 'documentFiles' folder and returns its URL. 
      The file is automatically added to the case's documents list.
    consumes:
      - multipart/form-data
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
      - in: formData
        name: file
        type: file
        required: true
        description: The file to upload (PDF, XML, or other document formats)
    responses:
      200:
        description: File uploaded successfully
        schema:
          $ref: '#/definitions/FileUploadResponse'
      400:
        description: Bad request - no file provided or invalid case ID
        schema:
          $ref: '#/definitions/ErrorResponse'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error during file upload
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    # Check authentication
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    caseData = get_case_by_id(case_id)
    if caseData is None:
        return jsonify({'success': False, 'message': 'Case not found'}), 404
    documents = caseData.get('documents', [])

    # Check file in request
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part in the request'}), 400

    file_as_blob = request.files['file'].read()
    sizeFlag = is_blob_under_12mb(file_as_blob)
    if not sizeFlag:
        return jsonify({'success': False, 'message': 'File is too large. Maximum size is 12MB'}), 400

    file_type = request.files['file'].content_type
    if file_type not in ['application/pdf', 'application/xml']:
        return jsonify({'success': False, 'message': 'Invalid file type. Only PDF and XML are allowed'}), 400
      
    file_name = request.files['file'].filename
    file = request.files['file']

    newEntryData = {
      'file_name': file_name,
      'file_type': file_type,
      'file_size': len(file_as_blob),
      'created_at': dt.now().isoformat(),
      'created_by': user_id,
      'case_id': case_id,
      'file_content': file_as_blob,
    }

    try:
      created_document = createDocument(newEntryData)
      newEntryData.pop('file_content')
      if created_document.get('success', False)==False:
        return jsonify({
          'success': False, 
          'message': created_document,
          'newEntryData': newEntryData
          }), 400
      document_id = created_document.get('document_id')
      document_url = f'document/{document_id}'
      documentEntry = {
        'url': document_url,
        'source': 'local'
      }
      newEntryData['document_created_response'] = created_document
      newEntryData['update_case_entry'] = documentEntry
      documents.append(documentEntry)
      updateData = {
        'documents': documents, 
        'last_updated': dt.now()
      }
      if len(documents) > 1:
        updateResult = update_case_documents(case_id, updateData)
      else:
        updateResult = update_case(case_id, updateData)
      newEntryData['update_case_result'] = updateResult
      if updateResult.get('success', False)==False:
        return jsonify({
          'success': False, 
          'message': 'Unable to update document id to case entry',
          'newEntryData': newEntryData
          }), 400
      return jsonify({
        'success': True,
        'message': 'File uploaded successfully',
        'document_id': document_id,
        'document_url': document_url
      })
    except Exception as e:
      print(f'LOG: Error uploading file: {str(e)}')
      newEntryData.pop('file_content')
      newEntryData['file_size_under12Mb'] = sizeFlag
      return jsonify({
        'success': False, 
        'message': f'Failed to upload file: {str(e)}',
        'newEntryData': newEntryData
        }), 500

@app.route('/api/alerts', methods=['GET'])
def get_all_alerts():
    """
    Get all alerts in the system
    ---
    tags:
      - Alerts
    summary: Get all alerts
    description: Returns all alerts in the system (admin/global view)
    produces:
      - application/json
    security:
      - session: []
    responses:
      200:
        description: Alerts retrieved successfully
        schema:
          $ref: '#/definitions/AlertsResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Get All Alerts')

    page = request.args.get('page', 1, type=int)
    try:
        results = get_alerts(page=page)
        return jsonify({
            'success': True,
            'items': results.get('items', []),
            'pagination': results.get('pagination', {})
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting all alerts: {str(e)}'}), 500

@app.route('/api/alerts/', methods=['GET'])
def get_user_alerts():
    """
    Get alerts for the current user
    ---
    tags:
      - Alerts
    summary: Get user-specific alerts with similarity analysis
    description: |
      Returns all alerts related to the authenticated user. Each alert includes similarity 
      analysis showing which of the user's cases are most similar to the alert-triggering case.
    produces:
      - application/json
    security:
      - session: []
    responses:
      200:
        description: User alerts retrieved successfully
        schema:
          $ref: '#/definitions/AlertsResponse'
      401:
        description: Not authenticated
        schema:
          $ref: '#/definitions/ErrorResponse'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    print(f'LOG: {user_id} Get User Alerts')
    page = request.args.get('page', 1, type=int)
    try:
        results = get_alerts_for_user(user_id, page=page)
        return jsonify({
            'success': True,
            'items': results.get('items', []),
            'pagination': results.get('pagination', {})
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting all alerts: {str(e)}'}), 500

@app.route('/api/trigger-similarity-analysis', methods=['POST'])
def trigger_similarity_analysis():
  """
  Trigger a similarity analysis for a specific case
  ---
  tags:
    - Similarity Analysis
  summary: Run similarity analysis for a specific case
  description: |
    Triggers a keyword-based similarity analysis for a given case. If no keywords are provided in the request, it will attempt to use the keywords from the case itself. 
    Retrieves similar USPTO documents and references using the keywords, generates and updates reports for the case, and creates an alert for the triggering user.
  consumes:
    - application/json
  produces:
    - application/json
  security:
    - session: []
  parameters:
    - in: body
      name: analysis_request
      description: Similarity analysis request data
      required: true
      schema:
        $ref: '#/definitions/SimilarityAnalysisRequest'
  responses:
    200:
      description: Similarity analysis completed and alert created successfully
      schema:
        $ref: '#/definitions/SimilarityAnalysisResponse'
    400:
      description: Bad request - missing user ID, data, or keywords
      schema:
        $ref: '#/definitions/ErrorResponse'
    500:
      description: Internal server error during similarity analysis
      schema:
        $ref: '#/definitions/ErrorResponse'
  """
  user_id = get_user_id()
  if not user_id:
      return jsonify({'success': False, 'message': 'Not authenticated'}), 401
  print(f'LOG: {user_id} Trigger Similarity Analysis')
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
    case_data['last_updated'] = dt.now()
    update_case(case_id, case_data)
    
    newAlertId = create_alert(user_id, case_id, references)
    add_to_alerts(
        triggered_by=user_id, 
        triggered_at=dt.utcnow().isoformat(), 
        alert_users=[user_id], 
        title='HETEROJUNCTION BIPOLAR TRANSISTOR', 
        description='Patent Expired Due to NonPayment of Maintenance Fees Under 37 CFR 1.362')
    print('New Alert ID:', newAlertId)
    return jsonify({'success': True, 'message': 'Similarity analysis completed', 'alert_id': newAlertId}), 200
  except Exception as e:
    print(f'Error triggering similarity analysis: {str(e)}')
    return jsonify({'success': False, 'message': f'Error triggering similarity analysis: {str(e)}'}), 500

@app.route('/api/case-keywords', methods=['POST'])
def get_case_keywords():
  """
  Extract keywords from a document or case information
  ---
  tags:
    - Similarity Analysis
  summary: Extract keywords from document or case data
  description: |
    Extracts keywords from a document URL, or from title/description if no URL is provided.
    Supports both USPTO documents (requires API key) and local documents.
    Uses online (OpenAI) or offline (TF-IDF) keyword extraction methods.
  consumes:
    - application/json
  produces:
    - application/json
  parameters:
    - in: body
      name: keyword_request
      description: Document or case information for keyword extraction
      required: true
      schema:
        $ref: '#/definitions/CaseKeywordsRequest'
  responses:
    200:
      description: Keywords extracted successfully
      schema:
        $ref: '#/definitions/KeywordsResponse'
    400:
      description: Bad request - missing document URL or title/description, or no keywords found
      schema:
        $ref: '#/definitions/ErrorResponse'
    500:
      description: Server error during keyword extraction
      schema:
        $ref: '#/definitions/ErrorResponse'
  """
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

@app.route('/api/create-patent', methods=['POST'])
def api_create_patent():
  try:
    # Check if the user is authenticated
    user_id = get_user_id()
    if not user_id:
      return jsonify({
        'success': False, 
        'message': 'User ID is required'
        }), 400

    # Check if the data is provided
    data = request.get_json()
    if not data:
      return jsonify({
        'success': False, 
        'message': 'No data provided'
        }), 400
    print(f'Create Patent Data by {user_id}: {json.dumps(data, indent=4)}')
    # patent_data = data.get('patent_data')

    # Check if the patent already exists
    patent_id = data.get('_id', None)
    if patent_id is not None:
      patent_data = get_case_by_id(patent_id)
      if patent_data is not None:
        return jsonify({'success': False, 'message': 'Patent already exists'}), 400

    data['created_by'] = user_id
    data['created_date'] = dt.now().strftime('%Y-%m-%d')
    created_patent = create_case(data)
    if 'DocumentCreationError' in created_patent['case_id']:
      return jsonify({'success': False, 'message': created_patent['case_id']}), 400
    print('\nLOG: Created Patent: ', created_patent, '\n')
    
    returnVal = {
      'success': True, 
      'message': 'Patent created successfully', 
      'case_id': created_patent['case_id'],
      'case_data': data
      }
    return jsonify(returnVal), 200
  except Exception as e:
    print(f'Error creating patent: {str(e)}')
    return jsonify({
      'success': False, 
      'message': f'Error creating patent: {str(e)}'
      }), 500

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
  user_id = get_user_id()
  if not user_id:
    print('\nUser ID is not in session')
    return jsonify({'success': False, 'message': 'User ID is not in session'}), 400
  print(f'LOG: {user_id} Import Patent from USPTO')
  
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

  # Check if the patent already exists
  if caseAlreadyExists(patent_id, user_id):
    return jsonify({'success': False, 'message': 'Patent already exists in your portfolio'}), 400
  
  print(f'\nFetching patent of ID {patent_id} from USPTO (key: {getEnvKey("uspto")}): {json.dumps(data, indent=4)}')

  update_user_fetching_patents(user_id, [patent_id], [], replace=True)
  thread = threading.Thread(
    target=fetchById,
    args=(app, patent_id, user_id),
    daemon=True,
  )
  thread.start()
  responseBody = {
    'success': True, 
    'message': 'Patent data import started', 
    'case_id': patent_id
  }
  return jsonify(responseBody), 200

@app.route('/api/bulk-fetch', methods=['POST'])
def bulk_fetch():
  """
  Bulk import patents from an uploaded Excel or CSV file
  ---
  tags:
    - Patents
  summary: Bulk fetch patents from file
  description: |
    Accepts a multipart file upload containing patent records and starts background
    import for each row. The file must be `.csv`, `.xlsx`, or `.xls` and the first
    two columns must be `patent_id` and `title` (case-insensitive). Additional
    columns are ignored.

    Each row is processed asynchronously via `fetchById`, which tries USPTO first,
    then Google Patents, then Free Patents Online. On acceptance, the user's
    `fetching_patents` list is replaced with all queued patent IDs so the client
    can poll profile progress.

    Returns 202 immediately after validation; import continues in background threads.
  consumes:
    - multipart/form-data
  produces:
    - application/json
  security:
    - session: []
  parameters:
    - in: formData
      name: file
      type: file
      required: true
      description: |
        Excel or CSV file with required headers `patent_id`, `title` in the first
        two columns. Example row: US12345678, Example Patent Title
  responses:
    202:
      description: File validated and batch processing started
      schema:
        type: object
        properties:
          success:
            type: boolean
            example: true
          message:
            type: string
            example: "Batch processing started successfully"
    400:
      description: |
        Bad request — not authenticated, missing/empty file, invalid file type,
        unreadable file, or headers do not start with patent_id and title
      schema:
        type: object
        properties:
          success:
            type: boolean
            example: false
          message:
            type: string
            example: "File headers must start with ['patent_id', 'title']"
  """
  # Check User ID
  user_id = get_user_id()
  if not user_id:
    print('\nUser ID is not in session')
    return jsonify({'success': False, 'message': 'User ID is not in session'}), 400
  print(f'LOG: {user_id} bulk fetch upload')

  # Check Excel/CSV File Exists
  if 'file' not in request.files:
    print('\nNo File provided')
    return jsonify({'success': False, 'message': 'No file provided'}), 400

  file = request.files['file']
  fileBytes = file.read()
  # Check file is not empty and filename is valid
  if file.filename == '' or not file:
    print('\nNo File selected')
    return jsonify({'success': False, 'message': 'No file selected'}), 400
  if not fileBytes:
    print('\nFile is empty')
    return jsonify({'success': False, 'message': 'File is empty'}), 400
  # Check file type is Excel/CSV
  allowed = False
  if file.filename.lower().endswith('.xlsx') or file.filename.lower().endswith('.csv') or file.filename.lower().endswith('.xls'):
    allowed = True
  if not allowed:
    print('\nInvalid file type')
    return jsonify({'success': False, 'message': 'Invalid file type'}), 400
  
  # Read file and check headers
  titles_in_order = ['patent_id', 'title']
  filename_lower = file.filename.lower()
  try:
    if filename_lower.endswith('.csv'):
      df = pd.read_csv(io.BytesIO(fileBytes))
    else:
      df = pd.read_excel(io.BytesIO(fileBytes))
  except Exception as e:
    print(f"\nError reading file: {e}")
    return jsonify({'success': False, 'message': f'Failed to read file: {e}'}), 400

  if df.shape[1] < 2:
    print('\nFile does not have at least two columns')
    return jsonify({'success': False, 'message': 'File does not have required headers'}), 400

  actual_headers = list(df.columns)
  if actual_headers[0].strip().lower() != titles_in_order[0].strip().lower() \
      or actual_headers[1].strip().lower() != titles_in_order[1].strip().lower():
    print('\nFile headers do not match required order')
    return jsonify({'success': False, 'message': f'File headers must start with {titles_in_order}'}), 400

  # Read the first 2 columns (without headers) from the file
  records = df.iloc[:, :2].values.tolist()
  # Isolate the patent_ids to a separate array
  patent_ids = [record[0] for record in records if len(record) >= 1]
  update_user_fetching_patents(user_id, patent_ids, [], replace=True)
  thread = threading.Thread(
    target=bulk_fetch_by_ids,
    args=(app, patent_ids, records, user_id),
    daemon=True,
  )
  thread.start()
  return jsonify({
    'success': True, 
    'message': 'Batch processing started successfully'}
    ), 202

@app.route('/api/get-claims/<case_id>', methods=['GET'])
def get_claims_for_patent(case_id):
  #TODO: Add function information to swagger
  user_id = get_user_id()
  if not user_id:
    print('\nUser ID is not in session')
    return jsonify({'success': False, 'message': 'User ID is not in session'}), 400
  print(f'LOG: {user_id} Getting Claims for Case: {case_id}')

  try:
    case_data = get_case_by_id(case_id)
    if case_data is None:
      print(f'\nERROR: Error getting claims: Case not found')
      return jsonify({'success': False, 'message': 'Case not found'}), 404

    existing_claims = case_data.get('claims', [])
    if (len(existing_claims) > 0) and (existing_claims is not None):
      print(f'\nERROR: Error getting claims: Claims already exist')
      return jsonify({'success': True, 'message': 'Claims already exist', 'claims': existing_claims}), 200

    description = case_data.get('description', '')
    if description.strip() != "":
      complete_document_contents = f"Description:\n{description}"
    
    document_urls = case_data.get('document_urls', [])
    document_contents = []
    for document in document_urls:
      if 'uspto' in document:
        content  = readDocumentFromUrl(document, headers={"X-API-KEY": getEnvKey('uspto')})
      elif '/document/' in document:
        doc_id = document.split('/')[-1].strip()
        content = readLocalDocument(doc_id)
      else:
        content = readDocumentFromUrl(document)
      document_contents.append(content)

    documents = case_data.get('documents', [])
    for document in documents:
      if document.get('source', '') == 'uspto':
        content  = readDocumentFromUrl(document.get('url', ''), headers={"X-API-KEY": getEnvKey('uspto')})
        document_contents.append(content)
      elif document.get('source', '') == 'local':
        doc_id = document.get('url', '').split('/')[-1].strip()
        document_view = getDocumentById(doc_id)
        if document_view.get('success', False):
          document_blob = document_view.get('document', {}).get('file_content', '')
          content = document_blob.decode('utf-8')
          document_contents.append(content)
      else:
        document_contents.append(document.get('content', ''))

    if (len(document_contents) == 0) or (document_contents is None):
      return jsonify({
        'success': False, 
        'message': 'No viable document contents provided', 
        'documents': {
          'document_urls_key': document_urls,
          'documents_key': document_contents
        }}), 400

    complete_document_contents = ""
    for content in document_contents:
      if content.strip() != "":
        complete_document_contents = f"{complete_document_contents}\n\n{content}"
    
    if complete_document_contents.strip() == "":
      print(f'\nERROR: Error getting claims: No viable document contents provided')
      return jsonify({'success': False, 'message': 'No viable document contents provided'}), 400

    claims = get_claims(complete_document_contents)
    if (len(claims) == 0) or (claims is None):
      print(f'\nERROR: Error getting claims: No claims found')
      return jsonify({'success': False, 'message': 'No claims found'}), 400
    if (claims[0] == 'Rate Exceeded Error') or (claims[0] == 'Access Forbidden Error') or (claims[0] == 'Authentication Error') or (claims[0] == 'Bad Request Error'):
        print(f'\nERROR: Error getting claims: {claims[0]}')
        return jsonify({'success': False, 'message': claims[0]}), 400

    # Update Claims in Case Data
    result = update_case(case_id, {'claims': claims, 'last_updated': dt.now()})
    if result['success']:
      return jsonify({'success': True, 'message': 'Claims updated successfully', 'claims': claims}), 200
    else:
      print(f'\nERROR: Error updating claims: {result["message"]}')
      return jsonify({'success': False, 'message': result['message']}), 400

  except Exception as e:
    print(f'\nERROR:Error getting claims data: {str(e)}')
    return jsonify({'success': False, 'message': f'Error getting claims for patent: {str(e)}'}), 500

# NOTE: Current implementation. Need to be updated with new one later after testing.
@app.route('/api/similarity-analysis-live/<case_id>', methods=['POST'])
def live_similarity_analysis(case_id):
  data = request.get_json()
  if data is None:
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  user_id = get_user_id()
  if not user_id:
    print('\nERROR: LiveSearch: User ID is not in session')
    return jsonify({'success': False, 'message': 'User ID is not in session'}), 400
  if 'keywords' not in data:
    print(f'\nERROR: LiveSearch: Keywords are required for user: {user_id}')
    return jsonify({'success': False, 'message': 'Keywords are required'}), 400
  if 'country' not in data:
    print(f'\nERROR: LiveSearch: Country is required for user: {user_id}')
    return jsonify({'success': False, 'message': 'Country is required'}), 400
  if 'claims' not in data:
    print(f'\nERROR: LiveSearch: Claims are required for user: {user_id}')
    return jsonify({'success': False, 'message': 'Claims are required'}), 400
  if 'owners' not in data:
    print(f'\nERROR: LiveSearch: Owners are required for user: {user_id}')
    return jsonify({'success': False, 'message': 'Owners are required'}), 400
  keywords = data.get('keywords', [])
  owners = data.get('owners', [])
  ref_claims = data.get('claims', [])
  country = data.get('country', '')
  context = data.get('context', '')
  search_limitations = data.get('search_limitations', {})
  
  if case_id is None:
    print(f'\nERROR: LiveSearch: Case ID is required for user: {user_id}')
    return jsonify({'success': False, 'message': 'Case ID is required'}), 400
  case_data = get_case_by_id(case_id)
  if case_data is None:
    print(f'\nERROR: LiveSearch: Case not found for user: {user_id}')
    return jsonify({'success': False, 'message': 'Case not found'}), 404
  
  keywords = case_data.get('keywords', [])
  ref_case_title = case_data.get('title', '')
  ref_case_id = case_data.get('_id', '').split('_')[-1]
  titles_to_avoid = case_data.get('excluded_case_titles', [])
  ids_to_avoid = case_data.get('excluded_case_ids', [])

  if (len(keywords) == 0) or (keywords is None):
    print(f'\nERROR: LiveSearch: Keywords are required for user: {user_id}')
    return jsonify({'success': False, 'message': 'Keywords are required'}), 400
  if (len(ref_claims) == 0) or (ref_claims is None):
    print(f'\nERROR: LiveSearch: Claims are required for user: {user_id}')
    return jsonify({'success': False, 'message': 'Claims are required'}), 400
  if (len(owners) == 0) or (owners is None):
    print(f'\nERROR: LiveSearch: Owners are required for user: {user_id}')
    return jsonify({'success': False, 'message': 'Owners are required'}), 400
  
  start_time = time.time()
  update_case(case_id, {'infringement_analysis_status': 'Started', 'last_updated': dt.now()})
  # Perform Live Patent Search
  try:
    patentResults, created_patent_ids = searchPatentSources(
      keywords, 
      country, 
      ref_claims, 
      ref_case_title, 
      ref_case_id
      )
    update_infringements(case_id, patentResults)
    update_case(
      case_id, 
      {
        'infringements': patentResults, 
        'infringement_analysis_status': 'Patent Sources Completed', 
        'infringement_details' : {
          'patent_ids' : created_patent_ids,
          'search_keywords' : keywords,
          'claim_type' : 'generic'
        },
        'last_infringement_analysis_date': dt.now(),
        'last_updated': dt.now()
        }
      )
  except Exception as e:
    current_time = time.time()
    time_in_seconds = current_time - start_time
    time_in_minutes = time_in_seconds // 60
    time_in_hours = int(time_in_minutes // 60)
    time_in_seconds = time_in_seconds % 60
    time_in_minutes = int(time_in_minutes % 60)
    update_case(case_id, {'infringement_analysis_status': 'Failed during Patent Sources', 'last_updated': dt.now()})
    print(f'\nERROR: LiveSearch: Error performing infringement analysis: {str(e)}')
    return jsonify({
      'success': False, 
      'message': f'Error performing patent source infringement analysis: {str(e)}',
      'execution_time': f"{time_in_hours}h {time_in_minutes}m {time_in_seconds}s"
      }), 500
  
  # Perform Live Product Search
  try:
    product_details_list, created_product_ids = searchProductSources(
      keywords, 
      owners, 
      ref_claims, 
      search_limitations
      )
    update_infringements(case_id, product_details_list)
    update_case(case_id, {'infringement_analysis_status': 'Product Sources Completed', 'last_updated': dt.now()})
    current_time = time.time()
    time_in_seconds = current_time - start_time
    time_in_minutes = time_in_seconds // 60
    time_in_hours = int(time_in_minutes // 60)
    time_in_seconds = time_in_seconds % 60
    time_in_minutes = int(time_in_minutes % 60)
    update_case(
      case_id, 
      {
        'infringement_analysis_status': 'Completed', 
        'infringement_details' : {
          'patent_ids' : created_patent_ids,
          'product_ids' : created_product_ids,
          'search_keywords' : keywords,
          'claim_type' : 'generic'
        },
        'last_infringement_analysis_date': dt.now(),
        'last_updated': dt.now()
        }
      )
    return jsonify({
      'success': True, 
      'message': 'Infringement analysis completed - Product Sources, Patent Sources', 
      'execution_time': f"{time_in_hours}h {time_in_minutes}m {time_in_seconds}s"
      }), 200
  except Exception as e:
    current_time = time.time()
    time_in_seconds = current_time - start_time
    time_in_minutes = time_in_seconds // 60
    time_in_hours = int(time_in_minutes // 60)
    time_in_seconds = time_in_seconds % 60
    time_in_minutes = int(time_in_minutes % 60)
    update_case(case_id, {'infringement_analysis_status': 'Failed during Product Sources', 'last_updated': dt.now()})
    print(f'\nERROR: LiveSearch: Error performing infringement analysis: {str(e)}')
    return jsonify({
      'success': False, 
      'message': f'Error performing product sourceinfringement analysis: {str(e)}',
      'search_results': product_details_list,
      'execution_time': f"{time_in_hours}h {time_in_minutes}m {time_in_seconds}s"
      }), 500

@app.route('/api/document/<document_id>', methods=['GET'])
def get_document(document_id):
  user_id = get_user_id()
  if not user_id:
    print('\nUser ID is not in session')
    return jsonify({'success': False, 'message': 'User ID is not in session'}), 400

  print(f'LOG: {user_id} Getting Document: {document_id}')
  document = getDocumentById(document_id)

  if document['success']:
    doc = document['document']
    raw = doc.get('file_content', None)
    if raw is None:
      return jsonify({'success': False, 'message': 'No raw data found'}), 400
    file_bytes = bytes(raw)

    file_type = doc.get('file_type', 'application/octet-stream')
    if not doc.get('file_name'):
      if file_type == 'application/pdf':
        file_name = 'local_document.pdf'
      elif file_type in ('application/xml', 'text/xml'):
        file_name = 'local_document.xml'
      else:
        file_name = 'document.bin'
    else:
      file_name = doc.get('file_name')

    if file_type == 'application/pdf':
      return Response(
        stream_with_context(chunk_generator(file_bytes)),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline; filename="{file_name}"'}
      ), 200
    if file_type in ('application/xml', 'text/xml'):
      return Response(
        stream_with_context(chunk_generator(file_bytes)),
        mimetype=file_type,
        headers={'Content-Disposition': f'inline; filename="{file_name}"'}
      ), 200
    return Response(
      stream_with_context(chunk_generator(file_bytes)),
      mimetype=file_type,
      headers={'Content-Disposition': f'attachment; filename="{file_name}"'}
    ), 200
  else:
    print(f"\nERROR: Error getting document: {document['message']}")
    return jsonify({'success': False, 'message': document['message']}), 400

@app.route('/api/proxy-document', methods=['POST'])
def get_document_content():
  data = request.get_json()
  if data is None:
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  if 'document_url' not in data:
    return jsonify({'success': False, 'message': 'Document URL is required'}), 400
  
  document_url = data.get('document_url', None)
  headers = {}

  if 'uspto' in document_url.lower():
    headers = {"X-API-KEY": getEnvKey('uspto')}
  try:  
    response = requests.get(document_url, headers=headers, stream=True)
    print(f'\nLOG: Streaming Document Content from USPTO : {response}')
    return Response(
      response.iter_content(chunk_size=8192), 
      content_type=response.headers.get('Content-Type', 'application/octet-stream')
      )
  except Exception as e:
    print(f'\nERROR: Error fetching document content: {str(e)}')
    return jsonify({'success': False, 'message': f'Error fetching document content: {str(e)}'}), 500

@app.route('/api/check-same-patent', methods=['POST'])
def check_same_patent():
  data = request.get_json()
  if data is None:
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  if 'case_title' not in data:
    return jsonify({'success': False, 'message': 'Case title is required'}), 400
  if 'infringement_title' not in data:
    return jsonify({'success': False, 'message': 'Infringement title is required'}), 400
  
  case_title = data.get('case_title', '').strip().lower()
  infringement_title = data.get('infringement_title', '').strip().lower()
  return jsonify({'success': True, 'message': 'Same patent check completed', 'same_as_patent': areSimilarStrings(case_title, infringement_title)}), 200

@app.route('/api/infringement-details/<case_id>', methods=['GET'])
def get_infringement_details(case_id):
  #TODO: Add function information to swagger
  user_id = get_user_id()
  if not user_id:
    print('\nUser ID is not in session')
    return jsonify({'success': False, 'message': 'User ID is not in session'}), 400
  print(f'LOG: {user_id} Getting Infringement Details for Case: {case_id}')
  try:
    case_data = get_case_by_id(case_id)
    if case_data is None:
      print(f'\nERROR: Error getting infringement details: Case not found')
      return jsonify({'success': False, 'message': 'Case not found'}), 404
    infringement_details = case_data.get('infringement_details', [])
    if (len(infringement_details) == 0) or (infringement_details is None):
      print(f'\nERROR: Error getting infringement details: No infringement details found')
      return jsonify({'success': False, 'message': 'No infringement details found'}), 400
    # Calculate Chart Data
    chart_data = []
    claims = case_data.get('claims', [])
    for claim in claims:
      infringement_count = 0
      infringing_ids = []
      for infringement in infringement_details:
        similar_claims = infringement.get('similar_claims', [])
        for similar_claim in similar_claims:
          current_claim = similar_claim.get('claim', '')

    return jsonify({
      'success': True, 
      'message': 'Infringement details retrieved successfully', 
      'infringement_details': {
        'title': case_data.get('title', ''),
        'claims': claims,
        'infringements': infringement_details
      }
      }), 200
  except Exception as e:
    print(f'\nERROR:Error getting infringement details data: {str(e)}')
    return jsonify({'success': False, 'message': f'Error getting infringement details for patent: {str(e)}'}), 500

@app.route('/api/generate-patent-summary/<case_id>', methods=['POST'])
def generate_patent_summary(case_id):
  data = request.get_json()
  if data is None:
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  
  case_data = get_case_by_id(case_id)
  if case_data is None:
    return jsonify({'success': False, 'message': 'Case not found'}), 404
  
  document_urls = case_data.get('document_urls', [])
  document_contents = []
  for document in document_urls:
    content  = readDocumentFromUrl(document, headers={"X-API-KEY": getEnvKey('uspto')})
    document_contents.append(content)

  if (len(document_contents) == 0) or (document_contents is None):
    return jsonify({'success': False, 'message': 'No viable document contents provided'}), 400

  complete_document_contents = ""
  for content in document_contents:
    if content.strip() != "":
      complete_document_contents = f"{complete_document_contents}\n\n{content}"
  
  if complete_document_contents.strip() == "":
    return jsonify({'success': False, 'message': 'No viable document contents provided'}), 400

  summary = get_patent_summary(complete_document_contents)
  return jsonify({
    'success': True, 
    'message': 'Patent summary generated successfully', 
    'summary': summary}), 200

@app.route('/api/generate-patent-description/<case_id>', methods=['POST'])
def generate_patent_description(case_id):
  data = request.get_json()
  if data is None:
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  
  case_data = get_case_by_id(case_id)
  if case_data is None:
    return jsonify({'success': False, 'message': 'Case not found'}), 404
  
  
  document_urls = case_data.get('document_urls', [])
  document_contents = []
  for document in document_urls:
    content  = readDocumentFromUrl(document, headers={"X-API-KEY": getEnvKey('uspto')})
    document_contents.append(content)
  
  if (len(document_contents) == 0) or (document_contents is None):
    return jsonify({'success': False, 'message': 'No viable document contents provided'}), 400
  
  complete_document_contents = ""
  for content in document_contents:
    if content.strip() != "":
      complete_document_contents = f"{complete_document_contents}\n\n{content}"
  
  if complete_document_contents.strip() == "":
    return jsonify({'success': False, 'message': 'No viable document contents provided'}), 400

  summary = get_patent_summary(complete_document_contents)
  
  # Update Case Data for the Generated Description
  result = update_case(case_id, {'description': summary, 'last_updated': dt.now()})
  print('TEST 6: Result')
  return jsonify({
    'success': True, 
    'message': 'Patent summary generated successfully', 
    'summary': summary}), 200

INFRINGEMENT_CHART_ERROR_RESPONSES = {
  'CASE_NOT_FOUND': (404, 'Case not found.'),
  'NO_PARENT_CLAIMS': (422, 'This case has no claims. Add claims before generating an infringement chart.'),
  'NO_INFRINGEMENTS': (422, 'No infringements have been added for this case yet.'),
  'INFRINGEMENT_CLAIMS_MISSING': (422, 'Infringements exist but contain no claims to compare.'),
}

@app.route('/api/infringement-chart/<case_id>', methods=['GET'])
def getInfringementChart(case_id):
  """
  Get infringement chart rows for a case.
  ---
  tags:
    - Infringements
  summary: Build chart data for parent-vs-infringing claims
  description: |
    Returns chart rows computed from case claims and stored infringing claims.
    Requires an authenticated session (user_id in session or X-User-ID header)
    and a case_id path parameter.

    The endpoint computes embedding cosine scores for every (parent claim ×
    infringing patent claim) pair, keeps pairs with score above the threshold,
    and stores them in `infringements[i].infringements` as an array of objects.
    A prior Gemini single-object analysis is copied to `gemini_infringement`
    when present. The response flattens all pairs into `chart_data`.

    On non-success, the response includes a machine-readable `error_code`:

      - `NO_SESSION` (401) — no user_id in session/header.
      - `CASE_NOT_FOUND` (404) — no case for the given case_id.
      - `NO_PARENT_CLAIMS` (422) — the case has no usable claims.
      - `NO_INFRINGEMENTS` (422) — the case has no infringements saved.
      - `INFRINGEMENT_CLAIMS_MISSING` (422) — infringements exist but none has
        claims populated.
      - `NO_MATCHES_ABOVE_THRESHOLD` (200) — pipeline ran but no pair met the
        similarity threshold; `chart_data` is `[]`.
      - `INTERNAL_ERROR` (500) — unhandled server error.
  security:
    - session: []
  parameters:
    - name: case_id
      in: path
      required: true
      type: string
      description: Unique case identifier.
  responses:
    200:
      description: |
        Pipeline ran successfully. `chart_data` contains the rows. When
        `error_code` is `NO_MATCHES_ABOVE_THRESHOLD`, the array is empty.
      schema:
        type: object
        properties:
          success:
            type: boolean
            example: true
          error_code:
            type: string
            example: NO_MATCHES_ABOVE_THRESHOLD
          chart_data:
            type: array
            items:
              type: object
              properties:
                ref_claim:
                  type: string
                  example: "1. A device comprising..."
                infringing_claim:
                  type: string
                  example: "A semiconductor device including..."
                similarity_score:
                  type: number
                  format: float
                  example: 0.81
                evaluation_method:
                  type: string
                  example: embedding_cosine
                last_evaluated:
                  type: string
                  example: "2026-05-01T15:30:00Z"
    401:
      description: Missing user session (`error_code: NO_SESSION`).
    404:
      description: Case not found (`error_code: CASE_NOT_FOUND`).
    422:
      description: |
        Case is missing data needed to build a chart. `error_code` is one of
        `NO_PARENT_CLAIMS`, `NO_INFRINGEMENTS`, or `INFRINGEMENT_CLAIMS_MISSING`.
    500:
      description: Internal server error (`error_code: INTERNAL_ERROR`).
  """
  user_id = get_user_id()
  if not user_id:
    print('\nERROR:User ID is not in session')
    return jsonify({
      'success': False,
      'error_code': 'NO_SESSION',
      'message': 'User ID is not in session',
    }), 401
  print(f'LOG: {user_id} Getting Infringement Chart for Case: {case_id}')
  try:
    infringement_chart, error_code = get_case_infringement_chart(case_id)
    rows_count = len(infringement_chart) if infringement_chart is not None else 0
    print(f'LOG: Infringement Chart rows: {rows_count} (error_code={error_code})')

    if error_code == 'NO_MATCHES_ABOVE_THRESHOLD':
      return jsonify({
        'success': True,
        'chart_data': [],
        'error_code': error_code,
        'message': 'No claim pairs met the similarity threshold.',
      }), 200

    if error_code is not None:
      status, message = INFRINGEMENT_CHART_ERROR_RESPONSES.get(
        error_code,
        (400, 'No infringement chart found. Please check Claims and Infringements'),
      )
      return jsonify({
        'success': False,
        'error_code': error_code,
        'message': message,
      }), status

    return jsonify({
      'success': True,
      'chart_data': infringement_chart,
    }), 200
  except Exception as e:
    print(f'\nERROR:Error getting infringement chart data: {str(e)}')
    return jsonify({
      'success': False,
      'error_code': 'INTERNAL_ERROR',
      'message': f'Error getting infringement chart for patent: {str(e)}',
    }), 500

@app.route('/api/test-new-infringement-analysis', methods=['POST'])
def test_new_infringement_analysis():
  data = request.get_json()
  if data is None:
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  if 'keywords' not in data:
    return jsonify({'success': False, 'message': 'Keywords are required'}), 400
  if 'country' not in data:
    return jsonify({'success': False, 'message': 'Country is required'}), 400
  
  search_results = searchPatentSourcesNew(data['keywords'], data['country'], data['claims'], data['context'])
  return jsonify({'success': True, 'message': 'New infringement analysis completed', 'search_results': search_results}), 200

@app.route('/api/search-history', methods=['GET'])
def get_search_history_route():
  user_id = get_user_id()
  if not user_id:
    return jsonify({'success': False, 'message': 'Not authenticated'}), 401
  page = request.args.get('page', 1, type=int)
  search_history = get_search_history(user_id, page=page)
  return jsonify({
      'success': True,
      'message': 'Search history retrieved successfully',
      'items': search_history.get('items', []),
      'pagination': search_history.get('pagination', {})
  }), 200

@app.route('/api/search', methods=['POST'])
def search():
  data = request.get_json()
  if data is None:
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  if 'search_query' not in data:
    return jsonify({'success': False, 'message': 'Search query is required'}), 400
  
  user_id = get_user_id()
  if not user_id:
    return jsonify({'success': False, 'message': 'Not authenticated'}), 401

  search_query = data.get('search_query', '')
  page = request.args.get('page', 1, type=int)
  search_results = search_cases(search_query, user_id, page=page)
  return jsonify({
    'success': True, 
    'message': 'Search completed successfully', 
    'items': search_results.get('items', []),
    'pagination': search_results.get('pagination', {})
    }), 200

@app.route('/api/add-search-history', methods=['POST'])
def add_search_history():
  data = request.get_json()
  if data is None:
    return jsonify({'success': False, 'message': 'No data provided'}), 400
  if 'search_query' not in data:
    return jsonify({'success': False, 'message': 'Search query is required'}), 400
  if 'search_results' not in data:
    return jsonify({'success': False, 'message': 'Search results are required'}), 400
  
  user_id = get_user_id()
  if not user_id:
    return jsonify({'success': False, 'message': 'Not authenticated'}), 401

  search_query = data.get('search_query', '')
  search_results = data.get('search_results', [])
  if (len(search_results) == 0) or (search_results is None):
    return jsonify({'success': False, 'message': 'No search results provided'}), 400
    
  added = add_search_history(user_id, search_query, search_results)
  if not added:
    return jsonify({'success': False, 'message': 'Failed to add search history'}), 400
  return jsonify({'success': True, 'message': 'Search history added successfully', 'search_results': search_results}), 200

# ─────────────────────────────────────────────────────────────────────────────
# Infringement CRUD endpoints
#
# All operations are case-scoped: every endpoint requires a case_id in the
# path and a user_id that resolves to an existing user. Bodies carry user_id
# for POST/PUT/DELETE; GET falls back to the X-User-ID header / session via
# get_user_id() for parity with the rest of the API.
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_infringement_request(case_id, body_data=None, require_body=False):
  """
  Shared validation for infringement routes.

  Returns ``(user_id, case, error_response)``. When ``error_response`` is not
  None, the route should return it directly.
  """
  if require_body and body_data is None:
    return None, None, (jsonify({'success': False, 'message': 'No data provided'}), 400)

  user_id = None
  if body_data is not None:
    user_id = body_data.get('user_id')
  if not user_id:
    user_id = get_user_id()
  if not user_id:
    return None, None, (jsonify({'success': False, 'message': 'user_id is required'}), 400)

  if get_user_profile(user_id) is None:
    return None, None, (jsonify({'success': False, 'message': 'User not found'}), 404)

  if not case_id:
    return None, None, (jsonify({'success': False, 'message': 'case_id is required'}), 400)

  case = get_case_by_id(case_id)
  if case is None:
    return None, None, (jsonify({'success': False, 'message': 'Case not found'}), 404)

  return user_id, case, None


@app.route('/api/cases/<case_id>/infringements', methods=['GET'])
def list_case_infringements(case_id):
  """
  List infringements for a case, optionally filtered by a created_at range.
  ---
  tags:
    - Infringements
  parameters:
    - name: case_id
      in: path
      required: true
      type: string
    - name: start_date
      in: query
      required: false
      type: string
      description: ISO-8601 timestamp; lower bound for created_at (inclusive).
    - name: end_date
      in: query
      required: false
      type: string
      description: ISO-8601 timestamp; upper bound for created_at (inclusive).
  responses:
    200:
      description: Infringements retrieved successfully.
    400:
      description: Missing user_id or case_id.
    404:
      description: User or case not found.
  """
  user_id, case, error = _resolve_infringement_request(case_id)
  if error is not None:
    return error
  print(f'LOG: {user_id} List Infringements for Case: {case_id}')

  start_date = request.args.get('start_date') or None
  end_date = request.args.get('end_date') or None

  if start_date or end_date:
    result = _model_get_infringements_by_created_date(case_id, start_date=start_date, end_date=end_date)
  else:
    result = _model_get_infringements_by_parent_case_id(case_id)

  status = 200 if result.get('success') else 500
  return jsonify(result), status


@app.route('/api/cases/<case_id>/infringements/<infringement_id>', methods=['GET'])
def get_case_infringement(case_id, infringement_id):
  """
  Fetch a single infringement scoped to the given case.
  ---
  tags:
    - Infringements
  parameters:
    - name: case_id
      in: path
      required: true
      type: string
    - name: infringement_id
      in: path
      required: true
      type: string
  responses:
    200:
      description: Infringement retrieved successfully.
    400:
      description: Missing user_id or case_id.
    404:
      description: User, case, or infringement not found.
  """
  user_id, case, error = _resolve_infringement_request(case_id)
  if error is not None:
    return error
  print(f'LOG: {user_id} Get Infringement {infringement_id} for Case: {case_id}')

  result = _model_get_infringement_by_id(infringement_id, parent_case_id=case_id)
  status = 200 if result.get('success') else 404
  return jsonify(result), status


@app.route('/api/cases/<case_id>/infringements/<infringement_id>', methods=['PUT'])
def update_case_infringement(case_id, infringement_id):
  """
  Update an existing infringement scoped to the given case.

  Body shape:
    { "user_id": str, "update_data": { ... } }
  ---
  tags:
    - Infringements
  parameters:
    - name: case_id
      in: path
      required: true
      type: string
    - name: infringement_id
      in: path
      required: true
      type: string
  responses:
    200:
      description: Infringement updated successfully.
    400:
      description: Missing user_id, case_id, or update_data.
    404:
      description: User, case, or infringement not found.
  """
  data = request.get_json(silent=True)
  user_id, case, error = _resolve_infringement_request(case_id, body_data=data, require_body=True)
  if error is not None:
    return error
  print(f'LOG: {user_id} Update Infringement {infringement_id} for Case: {case_id}')

  update_data = data.get('update_data')
  if not isinstance(update_data, dict) or len(update_data) == 0:
    return jsonify({'success': False, 'message': 'update_data must be a non-empty object'}), 400

  update_data.pop('_id', None)
  update_data.pop('parent_case_id', None)

  result = _model_update_infringement_by_id(infringement_id, update_data, parent_case_id=case_id)
  status = 200 if result.get('success') else 404
  return jsonify(result), status


@app.route('/api/cases/<case_id>/infringements/<infringement_id>', methods=['DELETE'])
def delete_case_infringement(case_id, infringement_id):
  """
  Delete a single infringement scoped to the given case.

  Body shape:
    { "user_id": str }
  ---
  tags:
    - Infringements
  parameters:
    - name: case_id
      in: path
      required: true
      type: string
    - name: infringement_id
      in: path
      required: true
      type: string
  responses:
    200:
      description: Infringement deleted successfully.
    400:
      description: Missing user_id or case_id.
    404:
      description: User, case, or infringement not found.
  """
  data = request.get_json(silent=True)
  user_id, case, error = _resolve_infringement_request(case_id, body_data=data)
  if error is not None:
    return error
  print(f'LOG: {user_id} Delete Infringement {infringement_id} for Case: {case_id}')

  result = _model_delete_infringement_by_id(infringement_id, parent_case_id=case_id)
  status = 200 if result.get('success') else 404
  return jsonify(result), status

if __name__ == '__main__':
    port = app.config['PORT']
    debug = app.config['DEBUG']
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
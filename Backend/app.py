from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
import os
from controller import *
from swagger import initialize_swagger, get_response_models

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

# API Endpoints
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
    
    try:
        user_id = session['user_id']
        cases = get_user_cases(user_id)
        return jsonify({
            'success': True,
            'cases': cases
        })
    except Exception as e:
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
    
    try:
        user_id = session['user_id']
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

    try:
        update_data = request.get_json()
        if not update_data:
            return jsonify({'success': False, 'message': 'No update data provided'}), 400

        # Assume update_case_by_id is a function that updates the case and returns the updated case or None if not found
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

if __name__ == '__main__':
    port = app.config['PORT']
    debug = app.config['DEBUG']
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

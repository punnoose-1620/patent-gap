from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
import os
from controller import *

app = Flask(__name__, 
            static_folder='../Assets',
            template_folder='../Frontend')
CORS(app)

# Set secret key for sessions
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Configuration
app.config['PORT'] = int(os.environ.get('PORT', 5000))
app.config['DEBUG'] = os.environ.get('DEBUG', 'True').lower() == 'true'

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

# API Endpoints
@app.route('/api/login', methods=['POST'])
def login():
    """Handle user login"""
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
    """Handle user logout"""
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully',
        'redirect': '/'
    })

@app.route('/api/my-cases')
def my_cases():
    """Get user's cases"""
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
    """Get open cases"""
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
    """Get user profile"""
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

@app.route('/api/cases/<case_id>')
def get_case_details(case_id):
    """Get detailed information about a specific case"""
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

@app.route('/api/cases/<case_id>/patents')
def get_case_patents(case_id):
    """Get related patents for a specific case"""
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
    """Verify if the entered password matches the user's current password"""
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
    """Change the user's password"""
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

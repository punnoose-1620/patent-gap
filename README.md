# Patent Gap - Flask Backend with HTML Frontend

A Flask-based web application for patent management with a modern HTML frontend.

## Project Structure

```
patent-gap/
├── Backend/                 # Python backend files
│   ├── app.py              # Main Flask application
│   ├── controller.py       # Business logic controllers
│   ├── swagger.py          # Swagger/OpenAPI configuration
│   └── env_example.txt     # Environment variables example
├── Frontend/               # HTML frontend files
│   ├── index.html          # Home page
│   ├── login.html          # Login page
│   ├── home.html           # Dashboard page
│   ├── case-details.html   # Case details page
│   └── styles.css          # Shared CSS styles
├── Assets/                 # Images, media, documents
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Features

- **Home Page**: Landing page with three feature cards showcasing the platform's capabilities
- **Login System**: Secure authentication with session management
- **Dashboard**: Personal dashboard with statistics and navigation to different sections
- **My Cases**: View and manage user's assigned cases with status tracking
- **Open Cases**: Browse and view available cases for assignment
- **Case Details**: Detailed view of individual cases with related patent information
- **Profile**: User profile management with case statistics
- **Related Patents**: View patents associated with specific cases
- **API Documentation**: Interactive Swagger UI for comprehensive API testing and exploration

## Setup Instructions

### Quick Installation (Recommended)

The installation scripts will automatically set up a virtual environment, install dependencies, create necessary directories, and generate run scripts.

#### For Linux/macOS:
```bash
# Make the script executable
chmod +x install.sh

# Run the installation script
./install.sh
```

#### For Windows:
```cmd
# Run the batch installation script
install.bat
```

#### For Windows PowerShell:
```powershell
# Set execution policy (if needed)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Run the PowerShell installation script
.\install.ps1
```

#### What the Installation Scripts Do:
- ✅ Check Python 3.7+ installation
- ✅ Create virtual environment (`venv/`)
- ✅ Install all dependencies from `requirements.txt`
- ✅ Create necessary directories (`Assets/`, `Backend/logs/`, etc.)
- ✅ Generate `.env` file from template
- ✅ Create convenient run scripts (`run.sh`, `run-dev.sh`, `stop.sh`)
- ✅ Set up proper file permissions

### Manual Installation

If you prefer to set up the environment manually or the installation scripts don't work for your system:

#### 1. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

#### 2. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt
```

**Dependencies included:**
- `Flask==2.3.3` - Web framework
- `Flask-CORS==4.0.0` - Cross-origin resource sharing
- `python-dotenv==1.0.0` - Environment variable management
- `flasgger==0.9.7.1` - Swagger UI integration for API documentation

#### 3. Environment Configuration

Copy the environment example file and configure your settings:

```bash
# Copy environment template
cp Backend/env_example.txt Backend/.env

# Edit the .env file with your preferred settings
# Default values:
# SECRET_KEY=your-secret-key-change-this-in-production
# PORT=5000
# DEBUG=True
# FLASK_ENV=development
```

#### 4. Create Necessary Directories

```bash
# Create required directories
mkdir -p Assets
mkdir -p Backend/logs
mkdir -p Frontend/assets
mkdir -p Frontend/css
mkdir -p Frontend/js
```

#### 5. Run the Backend Application

```bash
# Navigate to Backend directory
cd Backend

# Run the Flask application
python app.py
```

**Important Notes:**
- The Flask app must be run from the `Backend/` directory
- Make sure the virtual environment is activated before running
- The application will be available at `http://localhost:5000`
- Press `Ctrl+C` to stop the server

### Running the Application

#### Using Generated Scripts (After Installation)

After running the installation script, you can use the convenient run scripts:

- **Production mode**: `./run.sh` (Linux/macOS) or `run.bat` (Windows)
- **Development mode**: `./run-dev.sh` (Linux/macOS) or `run-dev.bat` (Windows)
- **PowerShell mode**: `.\run.ps1` (Windows PowerShell)
- **Stop application**: `./stop.sh` (Linux/macOS) or `stop.bat` (Windows)

#### Manual Backend Execution

If you prefer to run the backend manually or need to debug:

```bash
# 1. Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows

# 2. Navigate to Backend directory
cd Backend

# 3. Run the Flask application
python app.py
```

**Backend Server Details:**
- **Default URL**: `http://localhost:5000`
- **Host**: `0.0.0.0` (accessible from other devices on network)
- **Port**: `5000` (configurable via `.env` file)
- **Debug Mode**: Enabled by default in development
- **Auto-reload**: Enabled when `FLASK_DEBUG=1`

**Troubleshooting:**
- If port 5000 is busy, change `PORT` in `Backend/.env`
- Make sure you're in the `Backend/` directory when running `python app.py`
- Check that the virtual environment is activated
- Verify all dependencies are installed: `pip list`

### Testing Swagger Documentation

To verify that Swagger is properly set up and working:

1. **Start the backend server** (if not already running):
   ```bash
   cd Backend
   python app.py
   ```

2. **Open your browser** and navigate to:
   - **Swagger UI**: `http://localhost:5000/swagger/`
   - **OpenAPI JSON**: `http://localhost:5000/apispec.json`

3. **Verify functionality**:
   - Swagger UI should load with all API endpoints visible
   - You should see 9 API endpoints organized by categories
   - Each endpoint should have detailed documentation with examples
   - You can test endpoints directly from the interface

## Demo Credentials

For testing purposes, use these credentials:
- **Email**: admin@example.com
- **Password**: password123

## API Documentation

### Swagger UI Interface

The application includes comprehensive API documentation powered by Swagger UI. This provides an interactive interface to explore and test all API endpoints.

#### Accessing Swagger Documentation

Once the backend is running, you can access the API documentation at:

- **Swagger UI**: `http://localhost:5000/swagger/`
- **OpenAPI JSON Spec**: `http://localhost:5000/apispec.json`

#### Features of Swagger Documentation

- **Interactive API Testing**: Test endpoints directly from the browser
- **Request/Response Examples**: See example data for all endpoints
- **Authentication Support**: Test authenticated endpoints with session management
- **Schema Validation**: View detailed request/response schemas
- **Organized by Categories**: Endpoints grouped by functionality (Authentication, Cases, Profile, Patents)

#### Using Swagger UI

1. **Navigate to the Swagger UI**: Open `http://localhost:5000/swagger/` in your browser
2. **Explore Endpoints**: Click on any endpoint to expand its details
3. **Test Endpoints**: Click "Try it out" to test endpoints with real data
4. **View Schemas**: Check the "Models" section to see data structures
5. **Authentication**: Some endpoints require login - use the `/api/login` endpoint first

### API Endpoints

#### Authentication
- `POST /api/login` - User login
- `POST /api/logout` - User logout

#### Cases Management
- `GET /api/my-cases` - Get user's assigned cases
- `GET /api/open-cases` - Get available cases for assignment
- `GET /api/cases/<case_id>` - Get detailed information about a specific case
- `POST /api/cases/<case_id>/update-status` - Update case information (status, priority, etc.)

#### Profile Management
- `GET /api/profile` - Get user profile and statistics
- `POST /api/verify-password` - Verify current password
- `POST /api/change-password` - Change user password

#### Patent Information
- `GET /api/cases/<case_id>/patents` - Get related patents for a specific case

#### Web Pages
- `GET /` - Home page (landing page)
- `GET /login` - Login page
- `GET /home` - Dashboard page (requires authentication)
- `GET /case-details?id=<case_id>` - Case details page (requires authentication)

## Development Notes

- The application uses Flask sessions for authentication
- CORS is enabled for cross-origin requests
- All controller functions are currently using mock data
- The frontend uses vanilla JavaScript for API calls
- Responsive design works on desktop and mobile devices
- Case details page supports URL parameters for case ID (`?id=<case_id>`)
- Dashboard includes real-time statistics and case management
- Patent information is displayed in card format with expandable details
- **API Documentation**: Comprehensive Swagger UI with interactive testing capabilities
- **OpenAPI 2.0**: Full OpenAPI specification with detailed schemas and examples

## Future Enhancements

- Database integration (SQLite/PostgreSQL)
- Real user authentication system
- Case management functionality
- File upload capabilities
- Advanced search and filtering
- Email notifications
- User role management

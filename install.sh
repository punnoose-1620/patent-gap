#!/bin/bash

# Patent Gap - Installation Script
# This script sets up a virtual environment and installs all required dependencies

set -e  # Exit on any error

echo "🚀 Patent Gap - Installation Script"
echo "=================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.7"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python 3.7 or higher is required. Current version: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists. Removing old one..."
    rm -rf venv
fi

python3 -m venv venv
echo "✅ Virtual environment created"

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📚 Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ Dependencies installed from requirements.txt"
else
    echo "❌ requirements.txt not found!"
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p Assets
mkdir -p Backend/logs
mkdir -p Frontend/assets
mkdir -p Frontend/css
mkdir -p Frontend/js

# Create .env file if it doesn't exist
if [ ! -f "Backend/.env" ]; then
    echo "⚙️  Creating .env file..."
    if [ -f "Backend/env_example.txt" ]; then
        cp Backend/env_example.txt Backend/.env
        echo "✅ .env file created from template"
    else
        echo "⚠️  env_example.txt not found, creating basic .env file..."
        cat > Backend/.env << EOF
# Patent Gap Environment Configuration
SECRET_KEY=your-secret-key-change-this-in-production
PORT=5000
DEBUG=True
FLASK_ENV=development
EOF
        echo "✅ Basic .env file created"
    fi
else
    echo "✅ .env file already exists"
fi

# Set up executable permissions for Python files
echo "🔐 Setting executable permissions..."
chmod +x Backend/app.py
chmod +x Backend/controller.py

# Create a simple run script
echo "📝 Creating run script..."
cat > run.sh << 'EOF'
#!/bin/bash
# Patent Gap - Run Script

echo "🚀 Starting Patent Gap Application..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Change to Backend directory and run the app
cd Backend
python app.py
EOF

chmod +x run.sh

# Create a development run script
echo "📝 Creating development run script..."
cat > run-dev.sh << 'EOF'
#!/bin/bash
# Patent Gap - Development Run Script

echo "🚀 Starting Patent Gap Application (Development Mode)..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Set development environment variables
export FLASK_ENV=development
export FLASK_DEBUG=1

# Change to Backend directory and run the app
cd Backend
python app.py
EOF

chmod +x run-dev.sh

# Create a stop script
echo "📝 Creating stop script..."
cat > stop.sh << 'EOF'
#!/bin/bash
# Patent Gap - Stop Script

echo "🛑 Stopping Patent Gap Application..."

# Find and kill any running Flask processes
pkill -f "python.*app.py" || echo "No running Flask processes found"

echo "✅ Application stopped"
EOF

chmod +x stop.sh

# Display installation summary
echo ""
echo "🎉 Installation Complete!"
echo "========================"
echo ""
echo "📁 Project Structure:"
echo "   ├── venv/                 # Virtual environment"
echo "   ├── Backend/              # Python backend"
echo "   ├── Frontend/             # HTML frontend"
echo "   ├── Assets/               # Static assets"
echo "   ├── run.sh               # Production run script"
echo "   ├── run-dev.sh           # Development run script"
echo "   └── stop.sh              # Stop script"
echo ""
echo "🚀 To start the application:"
echo "   ./run.sh                  # Production mode"
echo "   ./run-dev.sh              # Development mode"
echo ""
echo "🛑 To stop the application:"
echo "   ./stop.sh"
echo ""
echo "🔧 To activate virtual environment manually:"
echo "   source venv/bin/activate"
echo ""
echo "📖 For more information, see README.md"
echo ""
echo "✅ Ready to go! Happy coding! 🎯"

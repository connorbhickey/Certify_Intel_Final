#!/bin/bash
# Build script for Certify Intel Desktop Application (Mac/Linux)
# This script bundles the Python backend and builds the Electron app

echo "========================================"
echo " Certify Intel Desktop Build Script"
echo "========================================"
echo ""

# Check for required tools
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "ERROR: Node.js/npm is not installed"
    exit 1
fi

# Set version from argument or default
VERSION=${1:-A}
echo "Building Version: $VERSION"
echo ""

# Step 1: Bundle Python backend
echo "[1/5] Bundling Python backend with PyInstaller..."
cd ../backend
pip3 install pyinstaller --quiet
pyinstaller certify_backend.spec --clean --noconfirm
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to bundle Python backend"
    exit 1
fi
cd ../desktop-app

# Step 2: Copy backend bundle
echo "[2/5] Copying backend bundle..."
mkdir -p backend-bundle
cp ../backend/dist/certify_backend backend-bundle/

# Step 3: Copy frontend files
echo "[3/5] Copying frontend files..."
mkdir -p frontend
cp -r ../frontend/* frontend/

# Step 4: Prepare data
echo "[4/5] Preparing data..."
mkdir -p data
if [ "$VERSION" == "A" ]; then
    echo "  Using Version A: With data and API keys"
    cp ../backend/competitors.db data/
    cp ../backend/.env data/
else
    echo "  Using Version B: Blank template"
    # Create empty database
    touch data/competitors.db
    # Create empty .env template
    echo "# API Configuration" > data/.env.template
    echo "OPENAI_API_KEY=" >> data/.env.template
    echo "NEWS_API_KEY=" >> data/.env.template
fi

# Step 5: Install npm dependencies and build
echo "[5/5] Building Electron application..."
npm install
if [ "$VERSION" == "A" ]; then
    BUILD_VERSION=A npm run build:mac
else
    BUILD_VERSION=B npm run build:mac
fi

echo ""
echo "========================================"
echo " Build Complete!"
echo "========================================"
echo ""
echo "Output: ./dist/"
ls -la dist/*.dmg 2>/dev/null

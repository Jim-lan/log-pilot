#!/bin/bash
set -e

# Define colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting LogPilot Development Environment Setup...${NC}"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies from services/ingestion-worker/requirements.txt..."
pip install -r services/ingestion-worker/requirements.txt

echo -e "${GREEN}Setup Complete!${NC}"
echo "To activate the environment, run:"
echo "source venv/bin/activate"

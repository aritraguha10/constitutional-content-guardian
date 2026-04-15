#!/bin/bash

# Constitutional Content Guardian - Environment Setup Script

echo "🚀 Setting up Constitutional Content Guardian environment..."

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo "📦 Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Download spaCy model for NER
echo "🧠 Downloading spaCy NER model..."
python -m spacy download en_core_web_sm

# Create .env from example
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update .env with your AWS credentials"
fi

# Create necessary directories
echo "📁 Creating directory structure..."
mkdir -p logs data/generated data/cache

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env with your AWS Bedrock credentials"
echo "2. Run: python -m pytest tests/ (to verify setup)"
echo "3. Run: streamlit run src/app.py (to launch demo)"

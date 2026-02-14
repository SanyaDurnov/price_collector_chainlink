#!/bin/bash

# Price Collector Service Setup Script for VPS
# Run this script on your VPS to set up the price collector

echo "🚀 Setting up Price Collector Service on VPS..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip3 first."
    exit 1
fi

echo "✅ Python 3 and pip3 are installed"

# Create project directory
mkdir -p price_collector_service
cd price_collector_service

echo "📁 Project directory created"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

echo "🐍 Virtual environment created and activated"

# Install dependencies
pip install -r requirements.txt

echo "📦 Dependencies installed"

# Create data and logs directories
mkdir -p data logs

echo "📁 Data and logs directories created"

# Make scripts executable
chmod +x *.py

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Run the service: python3 simple_price_service.py"
echo "2. Test the service: python3 test_simple_collector.py"
echo "3. Test the API: python3 test_simple_api.py"
echo ""
echo "🌐 API will be available at: http://your-vps-ip:8080"
echo "   - Health check: http://your-vps-ip:8080/health"
echo "   - Latest prices: http://your-vps-ip:8080/latest"
echo "   - Price by timestamp: http://your-vps-ip:8080/price/BTC?timestamp=1234567890"
echo ""
echo "🔧 Configuration file: config.json"
echo "📊 Data storage: data/prices.json"
echo "📝 Logs: logs/price_collector.log"
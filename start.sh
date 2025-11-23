#!/bin/bash

# Stock Analyzer - Initialization Script
# This script initializes and launches both frontend and backend servers

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Log file
LOG_FILE="$PROJECT_ROOT/startup.log"
> "$LOG_FILE"  # Clear log file

# Function to print colored messages
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$LOG_FILE"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to cleanup on exit
cleanup() {
    print_message "$YELLOW" "\n🛑 Shutting down servers..."
    
    # Kill backend process
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        print_message "$GREEN" "✓ Backend server stopped"
    fi
    
    # Kill frontend process
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
        print_message "$GREEN" "✓ Frontend server stopped"
    fi
    
    print_message "$GREEN" "👋 Cleanup complete. Goodbye!"
    exit 0
}

# Set up trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Check prerequisites
print_message "$BLUE" "🔍 Checking prerequisites..."

if ! command_exists python3; then
    print_message "$RED" "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

if ! command_exists npm; then
    print_message "$RED" "❌ npm is not installed. Please install Node.js and npm first."
    exit 1
fi

print_message "$GREEN" "✓ All prerequisites met"

# Backend Setup
print_message "$BLUE" "\n📦 Setting up backend..."
cd "$BACKEND_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_message "$YELLOW" "Creating Python virtual environment..."
    python3 -m venv venv
    print_message "$GREEN" "✓ Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Install/update backend dependencies
print_message "$YELLOW" "Installing backend dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
print_message "$GREEN" "✓ Backend dependencies installed"

# Start backend server
print_message "$BLUE" "\n🚀 Starting backend server..."
python app.py >> "$LOG_FILE" 2>&1 &
BACKEND_PID=$!
print_message "$GREEN" "✓ Backend server started (PID: $BACKEND_PID)"
print_message "$YELLOW" "   Backend running at: https://localhost:5000"

# Wait for backend to be ready
print_message "$YELLOW" "⏳ Waiting for backend to initialize..."
sleep 5

# Frontend Setup
print_message "$BLUE" "\n📦 Setting up frontend..."
cd "$FRONTEND_DIR"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    print_message "$YELLOW" "Installing frontend dependencies (this may take a few minutes)..."
    npm install >> "$LOG_FILE" 2>&1
    print_message "$GREEN" "✓ Frontend dependencies installed"
else
    print_message "$GREEN" "✓ Frontend dependencies already installed"
fi

# Start frontend server
print_message "$BLUE" "\n🚀 Starting frontend server..."
BROWSER=none npm start >> "$LOG_FILE" 2>&1 &
FRONTEND_PID=$!
print_message "$GREEN" "✓ Frontend server started (PID: $FRONTEND_PID)"
print_message "$YELLOW" "   Frontend running at: http://localhost:3000"

# Wait for frontend to be ready
print_message "$YELLOW" "⏳ Waiting for frontend to initialize..."
sleep 10

# Launch Chrome browser
print_message "$BLUE" "\n🌐 Launching Chrome browser..."

if command_exists google-chrome; then
    google-chrome --new-window http://localhost:3000 &
    print_message "$GREEN" "✓ Chrome launched"
elif command_exists chromium-browser; then
    chromium-browser --new-window http://localhost:3000 &
    print_message "$GREEN" "✓ Chromium launched"
elif [ -d "/Applications/Google Chrome.app" ]; then
    open -a "Google Chrome" http://localhost:3000
    print_message "$GREEN" "✓ Chrome launched"
else
    print_message "$YELLOW" "⚠️  Chrome not found. Please open http://localhost:3000 manually"
fi

# Display status
print_message "$GREEN" "\n✨ Stock Analyzer is ready!"
print_message "$BLUE" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_message "$GREEN" "Backend:  http://localhost:5000"
print_message "$GREEN" "Frontend: http://localhost:3000"
print_message "$BLUE" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_message "$YELLOW" "\n📝 Logs are being written to: $LOG_FILE"
print_message "$YELLOW" "Press Ctrl+C to stop all servers and exit"

# Keep script running
wait

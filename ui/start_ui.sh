#!/bin/bash
echo "========================================"
echo "  Regime State Visualization UI"
echo "========================================"
echo

# Change to script directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -f "../.venv/bin/activate" ]; then
    source ../.venv/bin/activate
else
    echo "Warning: Virtual environment not found at ../.venv"
    echo "Make sure you have activated your Python environment."
    echo
fi

# Start backend in background
echo "Starting backend server..."
cd ..
python -m ui.run_backend &
BACKEND_PID=$!
cd ui

# Wait for backend to start
echo "Waiting for backend to initialize..."
sleep 3

# Start frontend
echo "Starting frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo
echo "Frontend will be available at: http://localhost:5173"
echo

# Trap to kill backend when frontend exits
trap "kill $BACKEND_PID 2>/dev/null" EXIT

npm run dev

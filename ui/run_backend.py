#!/usr/bin/env python
"""Start the FastAPI backend server."""

import subprocess
import sys
from pathlib import Path

# Change to the project root directory
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    import uvicorn
    from ui.backend.api import app

    print("Starting Regime State Visualization API...")
    print("API will be available at: http://localhost:8000")
    print("API docs available at: http://localhost:8000/docs")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

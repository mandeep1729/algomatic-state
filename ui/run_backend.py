#!/usr/bin/env python
"""Start the FastAPI backend server."""

import sys
from pathlib import Path

# Change to the project root directory
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables before importing settings
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from config.settings import get_settings

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    port = settings.server.port
    host = settings.server.host

    print("Starting Regime State Visualization API...")
    print(f"API will be available at: http://localhost:{port}")
    print(f"API docs available at: http://localhost:{port}/docs")
    print()

    uvicorn.run("ui.backend.api:app", host=host, port=port, reload=True)

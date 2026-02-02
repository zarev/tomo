"""Vercel serverless entry point for FastAPI."""
import sys
import os

# Add the project root to the path so we can import backend
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set DATA_DIR to the project's data directory if not already set
if "DATA_DIR" not in os.environ:
    os.environ["DATA_DIR"] = os.path.join(project_root, "data")

from backend.main import app

# Vercel expects the ASGI app to be named 'app' or 'handler'
# FastAPI is ASGI-compatible, so we can export it directly
handler = app

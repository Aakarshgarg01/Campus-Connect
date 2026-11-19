# api/main.py
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.append(str(BASE_DIR))

# Import the FastAPI instance defined in backend/app/main.py
from app.main import app  # noqa: E402

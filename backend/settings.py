from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
EXPORT_DIR = DATA_DIR / "exports"
PROMPTS_PATH = DATA_DIR / "prompts.md"
PERSONA_PATH = DATA_DIR / "persona.md"
COMPANY_PATH = DATA_DIR / "company_profile.md"

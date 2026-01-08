from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Use env var for DATA_DIR if available, else default to relative path
if os.getenv("DATA_DIR"):
    DATA_DIR = Path(os.getenv("DATA_DIR"))
else:
    # Fallback for local dev: project_root/../../data
    DATA_DIR = PROJECT_ROOT.parents[1] / "data"

RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Files
SSYK_JSON_PATH = RAW_DATA_DIR / "the-ssyk-hierarchy-with-occupations.json"
SSYK_PARQUET_PATH = PROCESSED_DATA_DIR / "ssyk_data.parquet"

# SCB API
SCB_API_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0110/AM0110A/LoneSpridSektYrk4AN"

# OpenAI
_raw_openai_api_key = os.getenv("OPENAI_API_KEY")
OPENAI_API_KEY = _raw_openai_api_key.strip() if _raw_openai_api_key else None
EMBEDDING_MODEL = "text-embedding-3-small"

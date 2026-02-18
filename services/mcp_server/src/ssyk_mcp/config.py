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
SSYK_META_PATH = PROCESSED_DATA_DIR / "ssyk_data.meta.json"

# SCB API
SCB_API_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0110/AM0110A/LoneSpridSektYrk4AN"

# OpenAI
_raw_openai_api_key = os.getenv("OPENAI_API_KEY")
OPENAI_API_KEY = _raw_openai_api_key.strip() if _raw_openai_api_key else None

# Allow override for local testing / upgrades.
EMBEDDING_MODEL = (os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small").strip()

# Embedding dimensionality contract.
# We intentionally lock this to 1536 so the vector index stays small (and compatible
# with future storage backends that may impose limits).
EMBEDDING_DIM = 1536

# Azure OpenAI (preferred when set)
#
# Notes:
# - Azure OpenAI uses a *deployment name* in the `model=` field.
# - The ADK agent (LiteLLM) commonly expects AZURE_API_* env vars; we accept both.
_raw_azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_API_BASE")
AZURE_OPENAI_ENDPOINT = _raw_azure_endpoint.strip() if _raw_azure_endpoint else None

_raw_azure_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
AZURE_OPENAI_API_KEY = _raw_azure_key.strip() if _raw_azure_key else None

_raw_azure_version = os.getenv("AZURE_OPENAI_API_VERSION") or os.getenv("AZURE_API_VERSION")
AZURE_OPENAI_API_VERSION = _raw_azure_version.strip() if _raw_azure_version else None

_raw_azure_embed_deployment = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = (
    _raw_azure_embed_deployment.strip() if _raw_azure_embed_deployment else None
)

_raw_azure_chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
AZURE_OPENAI_CHAT_DEPLOYMENT = _raw_azure_chat_deployment.strip() if _raw_azure_chat_deployment else None

AZURE_OPENAI_ENABLED = bool(
    AZURE_OPENAI_ENDPOINT
    and AZURE_OPENAI_API_KEY
    and AZURE_OPENAI_API_VERSION
    and AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
)

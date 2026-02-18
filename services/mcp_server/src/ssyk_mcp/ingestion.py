import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.append(str(Path(__file__).parents[2] / "src"))

import json
import httpx
import pandas as pd
import numpy as np
from openai import OpenAI
import time
from typing import Any, List, Dict
from ssyk_mcp.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    AZURE_OPENAI_ENABLED,
    AZURE_OPENAI_ENDPOINT,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    SSYK_JSON_PATH,
    SSYK_META_PATH,
    SSYK_PARQUET_PATH,
)

try:
    from openai import AzureOpenAI  # type: ignore
except Exception:  # pragma: no cover
    AzureOpenAI = None  # type: ignore

try:
    from openai import RateLimitError as OpenAIRateLimitError  # type: ignore
except Exception:  # pragma: no cover
    OpenAIRateLimitError = None  # type: ignore

def download_ssyk_taxonomy():
    """Downloads the SSYK taxonomy JSON if it doesn't exist."""
    url = "https://data.jobtechdev.se/taxonomy/version/latest/query/the-ssyk-hierarchy-with-occupations/the-ssyk-hierarchy-with-occupations.json"
    
    if SSYK_JSON_PATH.exists():
        print(f"File already exists at {SSYK_JSON_PATH}")
        return

    print(f"Downloading SSYK taxonomy from {url}...")
    with httpx.Client() as client:
        response = client.get(url, follow_redirects=True)
        response.raise_for_status()
        
        with open(SSYK_JSON_PATH, "wb") as f:
            f.write(response.content)
    print("Download complete.")

def extract_ssyk_level_4(concepts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Recursively extracts SSYK Level 4 concepts."""
    results = []
    for concept in concepts:
        if concept.get("type") == "ssyk-level-4":
            aliases: List[str] = []
            for child in concept.get("narrower", []) or []:
                if isinstance(child, dict) and child.get("type") == "occupation-name":
                    label = (child.get("preferred_label") or "").strip()
                    if label:
                        aliases.append(label)

            results.append({
                "ssyk_code": concept.get("ssyk_code_2012"),
                "title": concept.get("preferred_label"),
                "description": concept.get("definition"),
                "id": concept.get("id"),
                "aliases": aliases,
            })
        
        if "narrower" in concept:
            results.extend(extract_ssyk_level_4(concept["narrower"]))
    return results

def generate_embeddings(texts: List[str], client: Any, model_name: str) -> List[List[float]]:
    """Generates embeddings for a list of texts."""
    # Use larger batches to reduce call rate (Azure rate limits are often call-based).
    batch_size = 256
    embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"Generating embeddings for batch {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}...")
        create_kwargs: dict[str, Any] = {
            "input": batch,
            "model": model_name,
            "dimensions": EMBEDDING_DIM,
        }

        # Keep retries short; if the embeddings provider is throttled, callers can
        # fall back to reusing existing embeddings from the current parquet.
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                try:
                    response = client.embeddings.create(**create_kwargs)
                except TypeError:
                    create_kwargs.pop("dimensions", None)
                    response = client.embeddings.create(**create_kwargs)
                except Exception as e:
                    msg = str(e).lower()
                    if "dimensions" in msg and ("unknown" in msg or "unrecognized" in msg or "unsupported" in msg):
                        create_kwargs.pop("dimensions", None)
                        response = client.embeddings.create(**create_kwargs)
                    else:
                        raise

                batch_embeddings = [data.embedding for data in response.data]
                embeddings.extend(batch_embeddings)
                break
            except Exception as e:
                is_rate_limit = False

                # Prefer structured checks when available.
                status_code = getattr(e, "status_code", None)
                if status_code is None and getattr(e, "response", None) is not None:
                    status_code = getattr(getattr(e, "response", None), "status_code", None)
                if status_code == 429:
                    is_rate_limit = True

                err_name = type(e).__name__.lower()
                if "ratelimit" in err_name:
                    is_rate_limit = True

                if OpenAIRateLimitError is not None and isinstance(e, OpenAIRateLimitError):
                    is_rate_limit = True

                if not is_rate_limit:
                    msg = str(e).lower()
                    if "ratelimit" in msg or "rate limit" in msg or "429" in msg:
                        is_rate_limit = True

                if not is_rate_limit or attempt >= max_attempts:
                    print(f"Error generating embeddings: {e}")
                    raise

                # Exponential backoff with a sensible floor for Azure's typical 60s guidance.
                sleep_s = 60.0
                print(
                    "Rate limited while generating embeddings; "
                    f"retrying in {sleep_s:.0f}s (attempt {attempt}/{max_attempts})..."
                )
                time.sleep(sleep_s)
            
    return embeddings

def run_ingestion():
    """Main ingestion function."""
    # 1. Download Data
    download_ssyk_taxonomy()
    
    # 2. Load and Parse JSON
    print("Parsing JSON...")
    with open(SSYK_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    concepts = data.get("data", {}).get("concepts", [])
    ssyk_items = extract_ssyk_level_4(concepts)
    
    print(f"Found {len(ssyk_items)} SSYK Level 4 occupations.")
    
    # 3. Prepare Data for Embedding
    # Embed title-like text only (title + aliases). Descriptions are long Swedish text and
    # can dominate the semantic signal for short/English queries.
    def _build_embedding_text(item: Dict[str, Any]) -> str:
        title = (item.get("title") or "").strip()
        aliases = item.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = []
        alias_text = "; ".join([str(a).strip() for a in aliases if str(a).strip()])
        if alias_text:
            return f"{title} ({alias_text})".strip()
        return title

    def _build_search_text(item: Dict[str, Any]) -> str:
        # Rich text for BM25: title + description + aliases.
        title = (item.get("title") or "").strip()
        description = (item.get("description") or "").strip()
        aliases = item.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = []
        alias_text = "; ".join([str(a).strip() for a in aliases if str(a).strip()])
        parts = [p for p in [title, description, alias_text] if p]
        return "\n".join(parts)

    texts_to_embed = [_build_embedding_text(item) for item in ssyk_items]
    
    # 4. Generate Embeddings
    if AZURE_OPENAI_ENABLED:
        if AzureOpenAI is None:
            raise RuntimeError(
                "Azure OpenAI is configured but AzureOpenAI client is not available in the installed openai package."
            )
        client: Any = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
        )
        model_name = AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
        print(f"Generating embeddings using Azure OpenAI deployment {model_name}...")
    else:
        if not OPENAI_API_KEY:
            raise ValueError(
                "No embeddings provider configured. Set Azure OpenAI vars (preferred) or OPENAI_API_KEY."
            )
        client = OpenAI(api_key=OPENAI_API_KEY)
        model_name = EMBEDDING_MODEL
        print(f"Generating embeddings using OpenAI model {model_name}...")

    try:
        embeddings = generate_embeddings(texts_to_embed, client, model_name)
    except Exception as e:
        # If we're being rate-limited, still rebuild the parquet with the improved
        # `search_text` (title+description+aliases) by reusing embeddings from the
        # existing parquet when possible.
        msg = str(e).lower()
        is_rate_limit = (
            "ratelimit" in msg
            or "rate limit" in msg
            or "429" in msg
            or "ratelimit" in type(e).__name__.lower()
            or getattr(e, "status_code", None) == 429
        )

        if is_rate_limit and SSYK_PARQUET_PATH.exists():
            print(
                "Warning: embedding generation was rate-limited; reusing existing embeddings "
                "from the current parquet to proceed with updated BM25 search_text."
            )
            old_df = pd.read_parquet(SSYK_PARQUET_PATH)
            if "embedding" not in old_df.columns:
                raise
            if "id" in old_df.columns:
                embed_by_id = dict(zip(old_df["id"].astype(str), old_df["embedding"].tolist()))
                embeddings = [embed_by_id.get(str(item.get("id"))) for item in ssyk_items]
            else:
                embed_by_code = dict(zip(old_df["ssyk_code"].astype(str), old_df["embedding"].tolist()))
                embeddings = [embed_by_code.get(str(item.get("ssyk_code"))) for item in ssyk_items]

            if any(v is None for v in embeddings):
                raise RuntimeError(
                    "Failed to reuse embeddings from existing parquet (missing ids/codes). "
                    "Re-run ingestion when rate limits allow."
                )
        else:
            raise

    embedding_dim = len(embeddings[0]) if embeddings else 0
    if embedding_dim != EMBEDDING_DIM:
        provider = "azure_openai" if AZURE_OPENAI_ENABLED else "openai"
        raise ValueError(
            "Embedding dimension mismatch during ingestion: expected "
            f"{EMBEDDING_DIM} but got {embedding_dim} from {provider}/{model_name}. "
            "Configure a text-embedding-3-small (1536-dim) model/deployment and re-run ingestion."
        )
    
    # 5. Create DataFrame and Save
    df = pd.DataFrame(ssyk_items)
    df["embedding"] = embeddings
    # Keep a rich BM25 field independent of embeddings.
    df["search_text"] = [_build_search_text(item) for item in ssyk_items]
    # Keep what we embedded for traceability/debugging.
    df["embedding_text"] = texts_to_embed
    
    print(f"Saving processed data to {SSYK_PARQUET_PATH}...")
    df.to_parquet(SSYK_PARQUET_PATH, index=False)

    try:
        meta = {
            "provider": "azure_openai" if AZURE_OPENAI_ENABLED else "openai",
            "model_or_deployment": model_name,
            "embedding_dim": embedding_dim,
        }
        SSYK_META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote embedding metadata to {SSYK_META_PATH}...")
    except Exception as e:
        print(f"Warning: failed to write metadata ({type(e).__name__}): {e}")

    print("Ingestion complete.")

if __name__ == "__main__":
    run_ingestion()

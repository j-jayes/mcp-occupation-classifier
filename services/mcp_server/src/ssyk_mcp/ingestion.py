import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.append(str(Path(__file__).parents[2] / "src"))

import json
import httpx
import pandas as pd
import numpy as np
from openai import OpenAI
from typing import Any, List, Dict
import time
from ssyk_mcp.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    AZURE_OPENAI_ENABLED,
    AZURE_OPENAI_ENDPOINT,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    SSYK_JSON_PATH,
    SSYK_PARQUET_PATH,
)

try:
    from openai import AzureOpenAI  # type: ignore
except Exception:  # pragma: no cover
    AzureOpenAI = None  # type: ignore

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
            results.append({
                "ssyk_code": concept.get("ssyk_code_2012"),
                "title": concept.get("preferred_label"),
                "description": concept.get("definition"),
                "id": concept.get("id")
            })
        
        if "narrower" in concept:
            results.extend(extract_ssyk_level_4(concept["narrower"]))
    return results

def generate_embeddings(texts: List[str], client: Any, model_name: str) -> List[List[float]]:
    """Generates embeddings for a list of texts."""
    # Batching to be safe, though OpenAI handles large batches well
    batch_size = 100
    embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"Generating embeddings for batch {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}...")
        try:
            response = client.embeddings.create(
                input=batch,
                model=model_name,
            )
            # Ensure the embeddings are in the same order as the input
            batch_embeddings = [data.embedding for data in response.data]
            embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            # Simple retry logic could be added here
            raise e
            
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
    # We'll embed "{title}: {description}"
    texts_to_embed = [f"{item['title']}: {item['description']}" for item in ssyk_items]
    
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

    embeddings = generate_embeddings(texts_to_embed, client, model_name)
    
    # 5. Create DataFrame and Save
    df = pd.DataFrame(ssyk_items)
    df["embedding"] = embeddings
    # Also keep the text used for embedding if needed, or just rely on title/desc
    df["search_text"] = texts_to_embed
    
    print(f"Saving processed data to {SSYK_PARQUET_PATH}...")
    df.to_parquet(SSYK_PARQUET_PATH, index=False)
    print("Ingestion complete.")

if __name__ == "__main__":
    run_ingestion()

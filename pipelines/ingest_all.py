import sys
from pathlib import Path

import json
import httpx
import pandas as pd
import numpy as np
from openai import OpenAI
from typing import List, Dict, Any
import time
import os
from config import SSYK_JSON_PATH, SSYK_PARQUET_PATH, OPENAI_API_KEY, EMBEDDING_MODEL, PROCESSED_DATA_DIR, SCB_API_URL

INCOME_STATS_PATH = PROCESSED_DATA_DIR / "income_stats.json"

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

def generate_embeddings(texts: List[str], client: OpenAI) -> List[List[float]]:
    """Generates embeddings for a list of texts using OpenAI."""
    batch_size = 100
    embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"Generating embeddings for batch {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}...")
        try:
            response = client.embeddings.create(
                input=batch,
                model=EMBEDDING_MODEL
            )
            batch_embeddings = [data.embedding for data in response.data]
            embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            raise e
            
    return embeddings

def fetch_all_income_stats(ssyk_codes: List[str]):
    """
    Fetches income statistics for ALL SSYK codes in one go (or batches) 
    and saves to a JSON file.
    """
    print("Fetching SCB metadata...")
    client = httpx.Client(timeout=30.0)
    
    # 1. Get Metadata
    try:
        response = client.get(SCB_API_URL)
        response.raise_for_status()
        metadata = response.json()
    except Exception as e:
        print(f"Failed to fetch metadata: {e}")
        return

    # Map codes
    code_to_text = {} # code -> text
    latest_year = "2023" # Default
    all_content_codes = []
    
    for variable in metadata.get("variables", []):
        if variable["code"] == "ContentsCode":
            values = variable["values"]
            value_texts = variable["valueTexts"]
            for code, text in zip(values, value_texts):
                code_to_text[code] = text
                all_content_codes.append(code)
        if variable["code"] == "Tid":
            latest_year = variable["values"][-1]

    print(f"Latest year: {latest_year}")
    print(f"Found {len(all_content_codes)} metrics.")

    if not all_content_codes:
        print("Could not resolve metric codes.")
        return

    # 2. Fetch Data in Batches (SCB might limit query size)
    # We can try fetching ALL sectors/genders for ALL occupations in one query?
    # Usually SCB limits the number of cells. 
    # Let's batch by 50 occupations.
    
    all_stats = {}
    batch_size = 50
    
    for i in range(0, len(ssyk_codes), batch_size):
        batch_codes = ssyk_codes[i:i+batch_size]
        print(f"Fetching income stats for batch {i//batch_size + 1}...")
        
        payload = {
            "query": [
                {
                    "code": "Yrke2012",
                    "selection": { "filter": "item", "values": batch_codes }
                },
                {
                    "code": "Sektor",
                    "selection": { "filter": "item", "values": ["0"] } # Samtliga
                },
                {
                    "code": "Kon",
                    "selection": { "filter": "item", "values": ["1+2"] } # Totalt
                },
                {
                    "code": "ContentsCode",
                    "selection": { "filter": "item", "values": all_content_codes }
                },
                {
                    "code": "Tid",
                    "selection": { "filter": "item", "values": [latest_year] }
                }
            ],
            "response": { "format": "json" }
        }
        
        try:
            resp = client.post(SCB_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            # Parse
            # SCB JSON-stat flat format:
            # data['data'] is a list of {key: [...], values: [...]}
            # The 'columns' list defines the order of dimensions (in 'key') and measures (in 'values').
            
            columns = data.get("columns", [])
            col_codes = [c["code"] for c in columns]
            
            try:
                yrke_idx = col_codes.index("Yrke2012")
            except ValueError:
                print("Unexpected column structure: 'Yrke2012' missing.")
                continue

            # Identify measure columns (metrics)
            # Measures are usually after dimensions and have type 'c'.
            measure_indices = [] # List of (index_in_values, metric_name)
            
            current_measure_idx = 0
            for col in columns:
                if col.get("type") == "c":
                    code = col["code"]
                    # Use the text description from metadata as the key
                    metric_name = code_to_text.get(code, code)
                    measure_indices.append((current_measure_idx, metric_name))
                    current_measure_idx += 1

            for item in data["data"]:
                keys = item["key"]
                values = item["values"]
                
                # yrke_idx points to the column index. 
                # Since keys only contain dimensions, we need to ensure we index keys correctly.
                # Assuming dimensions appear first in columns list.
                ssyk = keys[yrke_idx]
                
                if ssyk not in all_stats:
                    all_stats[ssyk] = {"year": latest_year}
                
                # Map values to metrics
                for val_idx, metric_name in measure_indices:
                    if val_idx < len(values):
                        val = values[val_idx]
                        if val and val != "..":
                            try:
                                all_stats[ssyk][metric_name] = int(val)
                            except ValueError:
                                all_stats[ssyk][metric_name] = val
                        
        except Exception as e:
            print(f"Error fetching batch: {e}")
            if isinstance(e, httpx.HTTPStatusError):
                 print(f"Response text: {e.response.text}")
            # Continue to next batch
            
        time.sleep(0.5) # Be nice to API

    # Save to JSON
    print(f"Saving income stats for {len(all_stats)} occupations to {INCOME_STATS_PATH}...")
    with open(INCOME_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2)

def run_ingestion():
    # 1. Taxonomy
    download_ssyk_taxonomy()
    
    print("Parsing JSON...")
    with open(SSYK_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    concepts = data.get("data", {}).get("concepts", [])
    ssyk_items = extract_ssyk_level_4(concepts)
    print(f"Found {len(ssyk_items)} SSYK Level 4 occupations.")
    
    # 2. Embeddings
    texts_to_embed = [f"{item['title']}: {item['description']}" for item in ssyk_items]
    
    print("Generating embeddings...")
    client = OpenAI(api_key=OPENAI_API_KEY)
    embeddings = generate_embeddings(texts_to_embed, client)
    
    # 3. Save to Parquet
    print("Saving to Parquet...")
    df = pd.DataFrame(ssyk_items)
    df["embedding"] = embeddings
    
    # Ensure directory exists
    SSYK_PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SSYK_PARQUET_PATH)
    print(f"Saved {len(df)} records to {SSYK_PARQUET_PATH}")

    # 4. Fetch Income Stats
    print("Fetching income stats...")
    ssyk_codes = [item["ssyk_code"] for item in ssyk_items if item.get("ssyk_code")]
    fetch_all_income_stats(ssyk_codes)
    
    print("Ingestion complete!")

if __name__ == "__main__":
    run_ingestion()

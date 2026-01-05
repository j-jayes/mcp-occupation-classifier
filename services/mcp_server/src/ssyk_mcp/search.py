import pandas as pd
import numpy as np
from rank_bm25 import BM25Okapi
from openai import OpenAI
from typing import List, Dict, Any
from .config import SSYK_PARQUET_PATH, OPENAI_API_KEY, EMBEDDING_MODEL
import os

class SearchEngine:
    def __init__(self):
        self.df = None
        self.bm25 = None
        self.client = None
        self.is_ready = False

    def load_data(self):
        """Loads data and initializes indexes."""
        if not SSYK_PARQUET_PATH.exists():
            print(f"Data file not found at {SSYK_PARQUET_PATH}. Please run ingestion.")
            return

        print("Loading SSYK data...")
        self.df = pd.read_parquet(SSYK_PARQUET_PATH)
        
        # Initialize BM25
        # Tokenize titles for BM25
        tokenized_corpus = [doc.lower().split() for doc in self.df["title"].tolist()]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        # Initialize OpenAI Client
        if OPENAI_API_KEY:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        
        self.is_ready = True
        print("Search engine initialized.")

    def _get_embedding(self, text: str) -> List[float]:
        if not self.client:
            raise ValueError("OpenAI client not initialized.")
        
        response = self.client.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL
        )
        return response.data[0].embedding

    def _cosine_similarity(self, vec1, matrix):
        """Computes cosine similarity between a vector and a matrix of vectors."""
        vec1 = np.array(vec1)
        matrix = np.vstack(matrix)
        
        norm_vec1 = np.linalg.norm(vec1)
        norm_matrix = np.linalg.norm(matrix, axis=1)
        
        dot_products = np.dot(matrix, vec1)
        similarities = dot_products / (norm_vec1 * norm_matrix)
        return similarities

    def search(self, query: str, n: int = 5) -> List[Dict[str, Any]]:
        if not self.is_ready:
            self.load_data()
            if not self.is_ready:
                return []

        # 1. BM25 Search
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # 2. Vector Search
        try:
            query_embedding = self._get_embedding(query)
            vector_scores = self._cosine_similarity(query_embedding, self.df["embedding"].values)
        except Exception as e:
            print(f"Vector search failed: {e}")
            vector_scores = np.zeros(len(self.df))

        # 3. Hybrid Fusion (Weighted Sum or RRF)
        # Let's use a simple weighted sum after normalization
        
        def normalize(scores):
            if np.max(scores) == np.min(scores):
                return np.zeros_like(scores)
            return (scores - np.min(scores)) / (np.max(scores) - np.min(scores))

        norm_bm25 = normalize(bm25_scores)
        norm_vector = normalize(vector_scores)
        
        # Weighting: 0.3 BM25 + 0.7 Vector (Semantic is usually better for descriptions)
        final_scores = 0.3 * norm_bm25 + 0.7 * norm_vector
        
        # Get top N indices
        top_indices = np.argsort(final_scores)[::-1][:n]
        
        results = []
        for idx in top_indices:
            row = self.df.iloc[idx]
            results.append({
                "ssyk_code": row["ssyk_code"],
                "title": row["title"],
                "description": row["description"],
                "score": float(final_scores[idx])
            })
            
        return results

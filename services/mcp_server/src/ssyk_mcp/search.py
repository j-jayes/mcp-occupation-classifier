import numpy as np
import pandas as pd
import httpx
from openai import OpenAI
from rank_bm25 import BM25Okapi
import re
from typing import Any, Dict, List
import socket

from .config import EMBEDDING_MODEL, OPENAI_API_KEY, SSYK_PARQUET_PATH

class SearchEngine:
    def __init__(self):
        self.df = None
        self.bm25 = None
        self.client = None
        self.is_ready = False
        self._warned_embedding_disabled = False
        self._warned_vector_failure = False

    _TOKEN_RE = re.compile(r"[0-9a-zA-ZåäöÅÄÖ]+", re.UNICODE)

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        return [t.lower() for t in cls._TOKEN_RE.findall(text or "")]

    def load_data(self):
        """Loads data and initializes indexes."""
        if not SSYK_PARQUET_PATH.exists():
            print(f"Data file not found at {SSYK_PARQUET_PATH}. Please run ingestion.")
            return

        print("Loading SSYK data...")
        self.df = pd.read_parquet(SSYK_PARQUET_PATH)
        
        # Initialize BM25
        # Prefer embedding/semantic text if present (title + description), else fallback to title.
        if "search_text" in self.df.columns:
            corpus_texts = self.df["search_text"].fillna("").astype(str).tolist()
        else:
            corpus_texts = self.df["title"].fillna("").astype(str).tolist()

        tokenized_corpus = [self._tokenize(doc) for doc in corpus_texts]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        # Initialize OpenAI Client (optional)
        if OPENAI_API_KEY:
            # Use an explicit httpx client to control timeouts and avoid any
            # environment-dependent defaults.
            http_client = httpx.Client(
                timeout=httpx.Timeout(30.0, connect=10.0),
                http2=False,
            )
            self.client = OpenAI(api_key=OPENAI_API_KEY, http_client=http_client)
        
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

        query = (query or "").strip()
        if query == "":
            return []

        # 1. BM25 Search
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # 2. Vector Search (optional)
        vector_scores = None
        if self.client is None:
            if not self._warned_embedding_disabled:
                print(
                    "Vector search disabled (OPENAI_API_KEY not set). "
                    "Falling back to BM25-only search."
                )
                self._warned_embedding_disabled = True
        else:
            try:
                query_embedding = self._get_embedding(query)
                vector_scores = self._cosine_similarity(query_embedding, self.df["embedding"].values)
            except Exception as e:
                # Keep this on one line for Cloud Run logs, but include the type for debugging.
                print(f"Vector search failed ({type(e).__name__}): {e}")
                if not self._warned_vector_failure:
                    self._warned_vector_failure = True
                    try:
                        addrs = socket.getaddrinfo("api.openai.com", 443)
                        ips = sorted({a[4][0] for a in addrs})
                        print(f"OpenAI DNS api.openai.com -> {ips[:8]}")
                    except Exception as dns_e:
                        print(f"OpenAI DNS check failed ({type(dns_e).__name__}): {dns_e}")

                    try:
                        resp = httpx.get(
                            "https://api.openai.com/v1/models",
                            timeout=httpx.Timeout(10.0, connect=5.0),
                            follow_redirects=False,
                            headers={"Accept": "application/json"},
                        )
                        print(
                            "OpenAI HTTP probe ok "
                            f"status={resp.status_code} content_type={resp.headers.get('content-type')}"
                        )
                    except Exception as http_e:
                        print(f"OpenAI HTTP probe failed ({type(http_e).__name__}): {http_e}")
                vector_scores = None

        # 3. Hybrid Fusion (Weighted Sum or RRF)
        # Let's use a simple weighted sum after normalization
        
        def normalize(scores):
            if np.max(scores) == np.min(scores):
                return np.zeros_like(scores)
            return (scores - np.min(scores)) / (np.max(scores) - np.min(scores))

        norm_bm25 = normalize(bm25_scores)

        if vector_scores is None:
            # BM25-only fallback
            final_scores = norm_bm25
        else:
            norm_vector = normalize(vector_scores)
            # Weighting: 0.3 BM25 + 0.7 Vector (Semantic is usually better for descriptions)
            final_scores = 0.3 * norm_bm25 + 0.7 * norm_vector

        # If everything is zero, avoid returning arbitrary tail rows.
        if np.max(final_scores) <= 0:
            return []
        
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

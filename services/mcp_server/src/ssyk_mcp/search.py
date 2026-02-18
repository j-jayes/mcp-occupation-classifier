import numpy as np
import pandas as pd
import httpx
from openai import OpenAI
from rank_bm25 import BM25Okapi
import re
import threading
from typing import Any, Dict, List
import socket

from .config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    AZURE_OPENAI_ENABLED,
    AZURE_OPENAI_ENDPOINT,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    SSYK_PARQUET_PATH,
    SSYK_META_PATH,
)

try:
    from openai import AzureOpenAI  # type: ignore
except Exception:  # pragma: no cover
    AzureOpenAI = None  # type: ignore

class SearchEngine:
    def __init__(self):
        self.df = None
        self.bm25 = None
        self.client = None
        self.is_ready = False
        self._warned_embedding_disabled = False
        self._warned_vector_failure = False
        self._load_lock = threading.Lock()
        self._embedding_matrix = None
        self._index_embedding_dim: int | None = None
        self._index_embedding_model_or_deployment: str | None = None
        self._warned_embedding_dim_mismatch = False

    _TOKEN_RE = re.compile(r"[0-9a-zA-ZåäöÅÄÖ]+", re.UNICODE)

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        return [t.lower() for t in cls._TOKEN_RE.findall(text or "")]

    def load_data(self):
        """Loads data and initializes indexes."""
        if self.is_ready:
            return

        with self._load_lock:
            if self.is_ready:
                return

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

        # Pre-build embedding matrix (if present) once.
        self._embedding_matrix = None
        self._index_embedding_dim = None
        self._index_embedding_model_or_deployment = None
        if "embedding" in self.df.columns:
            try:
                raw_embeddings = self.df["embedding"].tolist()
                matrix = np.asarray(raw_embeddings, dtype=np.float32)
                if matrix.ndim != 2:
                    raise ValueError(f"Expected 2D embedding matrix, got shape={matrix.shape}")

                self._index_embedding_dim = int(matrix.shape[1])

                if SSYK_META_PATH.exists():
                    try:
                        import json

                        meta = json.loads(SSYK_META_PATH.read_text(encoding="utf-8"))
                        if isinstance(meta, dict):
                            model_or_deployment = meta.get("model_or_deployment")
                            if isinstance(model_or_deployment, str) and model_or_deployment.strip():
                                self._index_embedding_model_or_deployment = model_or_deployment.strip()
                    except Exception as meta_e:
                        print(
                            f"Warning: failed to read embedding metadata ({type(meta_e).__name__}): {meta_e}"
                        )

                norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                self._embedding_matrix = matrix / norms
            except Exception as e:
                print(f"Failed to initialize embedding matrix ({type(e).__name__}): {e}")
                self._embedding_matrix = None
        
        # Initialize embeddings client (optional)
        # Prefer Azure OpenAI when configured, else fallback to OpenAI.
        http_client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            http2=False,
        )

        self._using_azure_openai = False
        if AZURE_OPENAI_ENABLED:
            if AzureOpenAI is None:
                raise RuntimeError(
                    "Azure OpenAI is configured but AzureOpenAI client is not available in the installed openai package."
                )
            self.client = AzureOpenAI(
                api_key=AZURE_OPENAI_API_KEY,
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_version=AZURE_OPENAI_API_VERSION,
                http_client=http_client,
            )
            self._using_azure_openai = True
        elif OPENAI_API_KEY:
            self.client = OpenAI(api_key=OPENAI_API_KEY, http_client=http_client)
        
        self.is_ready = True
        print("Search engine initialized.")

    def _get_embedding(self, text: str) -> List[float]:
        if not self.client:
            raise ValueError("OpenAI client not initialized.")

        model_name = (
            AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT if getattr(self, "_using_azure_openai", False) else EMBEDDING_MODEL
        )
        
        # Enforce embedding dimensionality at request-time when supported.
        # (OpenAI supports `dimensions` for v3 embedding models; Azure support depends on API version.)
        create_kwargs: dict[str, Any] = {
            "input": text,
            "model": model_name,
            "dimensions": EMBEDDING_DIM,
        }
        try:
            response = self.client.embeddings.create(**create_kwargs)
        except TypeError:
            # Older clients/backends may not accept `dimensions`.
            create_kwargs.pop("dimensions", None)
            response = self.client.embeddings.create(**create_kwargs)
        except Exception as e:
            # Some backends reject unknown fields with a 400; retry without dimensions.
            msg = str(e).lower()
            if "dimensions" in msg and ("unknown" in msg or "unrecognized" in msg or "unsupported" in msg):
                create_kwargs.pop("dimensions", None)
                response = self.client.embeddings.create(**create_kwargs)
            else:
                raise
        embedding = response.data[0].embedding
        if len(embedding) != EMBEDDING_DIM:
            provider = "azure_openai" if getattr(self, "_using_azure_openai", False) else "openai"
            raise ValueError(
                "Embedding dimension mismatch: expected "
                f"{EMBEDDING_DIM} but got {len(embedding)} from {provider}/{model_name}. "
                "Use a text-embedding-3-small (1536-dim) model/deployment consistently for both ingestion and search."
            )
        return embedding

    def _cosine_similarity(self, vec1, matrix):
        """Computes cosine similarity between a vector and a matrix of vectors."""
        vec1 = np.asarray(vec1, dtype=np.float32)
        norm_vec1 = np.linalg.norm(vec1)
        if norm_vec1 == 0:
            return np.zeros((matrix.shape[0],), dtype=np.float32)
        vec1 = vec1 / norm_vec1
        return matrix @ vec1

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
        elif self._embedding_matrix is None:
            # Embeddings aren't available in the dataset (or failed to load).
            vector_scores = None
        else:
            try:
                query_embedding = self._get_embedding(query)
                query_dim = len(query_embedding)
                index_dim = self._embedding_matrix.shape[1]
                if query_dim != index_dim:
                    if not self._warned_embedding_dim_mismatch:
                        self._warned_embedding_dim_mismatch = True

                        provider = "azure_openai" if getattr(self, "_using_azure_openai", False) else "openai"
                        query_model = (
                            AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
                            if getattr(self, "_using_azure_openai", False)
                            else EMBEDDING_MODEL
                        )
                        index_model = self._index_embedding_model_or_deployment or "(unknown)"
                        print(
                            "Vector search disabled due to embedding dimension mismatch "
                            f"(query_dim={query_dim} index_dim={index_dim}). "
                            f"Query provider/model={provider}/{query_model}; index built with {index_model}. "
                            "Re-run ingestion to rebuild embeddings with the same model/deployment."
                        )
                    vector_scores = None
                else:
                    vector_scores = self._cosine_similarity(query_embedding, self._embedding_matrix)
            except Exception as e:
                # Keep this on one line for Cloud Run logs, but include the type for debugging.
                print(f"Vector search failed ({type(e).__name__}): {e}")
                if not self._warned_vector_failure:
                    self._warned_vector_failure = True
                    # Avoid probing api.openai.com when running on Azure OpenAI.
                    if not getattr(self, "_using_azure_openai", False):
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
            # Cosine similarity can be negative; for retrieval we treat negative similarity as no-signal.
            vector_scores = np.maximum(vector_scores, 0)
            norm_vector = normalize(vector_scores)

            # Adaptive weighting based on retriever confidence.
            # - Short (title-like) queries tend to benefit more from embeddings.
            # - When BM25 is confident (e.g., exact synonym match), it should dominate.
            conf_bm25 = float(np.max(norm_bm25)) if norm_bm25.size else 0.0
            conf_vec = float(np.max(norm_vector)) if norm_vector.size else 0.0

            token_count = len(tokenized_query)
            vec_floor = 0.35 if token_count <= 3 else 0.20
            if conf_bm25 >= 0.85:
                vec_floor = 0.05
            elif conf_bm25 >= 0.70:
                vec_floor = min(vec_floor, 0.15)
            vec_cap = 0.80
            eps = 1e-6
            w_vec = conf_vec / (conf_vec + conf_bm25 + eps)
            w_vec = float(np.clip(w_vec, vec_floor, vec_cap))
            w_bm25 = 1.0 - w_vec

            final_scores = w_bm25 * norm_bm25 + w_vec * norm_vector

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

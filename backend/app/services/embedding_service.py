import os
import numpy as np
import hashlib
from typing import List
from app.config import settings

class EmbeddingService:
    def __init__(self):
        self.is_testing = os.environ.get("TESTING") == "True"
        self.use_openai = bool(settings.OPENAI_API_KEY) and not self.is_testing
        self.local_model = None
        
        self._local_model_loaded = False
        
        if self.use_openai:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as e:
                print(f"Failed to initialize OpenAI client: {e}. Falling back to local/mock embeddings.")
                self.use_openai = False

    def _get_local_model(self):
        if not self._local_model_loaded and not self.use_openai and not self.is_testing:
            self._local_model_loaded = True
            try:
                from sentence_transformers import SentenceTransformer
                print(f"Loading local embedding model: {settings.EMBEDDING_MODEL}")
                self.local_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            except Exception as e:
                print(f"SentenceTransformers load failed: {e}. Using deterministic mock embedding generator.")
                self.local_model = None
        return self.local_model

    def get_embedding(self, text: str) -> List[float]:
        """Generates embedding for a single text input."""
        return self.get_embeddings([text])[0]

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of text inputs."""
        if not texts:
            return []
            
        if self.use_openai:
            try:
                # Use standard OpenAI text-embedding-3-large (3072 dims) or text-embedding-ada-002 (1536 dims)
                response = self.client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=texts
                )
                return [data.embedding for data in response.data]
            except Exception as e:
                print(f"OpenAI embedding generation failed: {e}. Falling back...")
                
        local_model = self._get_local_model()
        if local_model:
            try:
                embeddings = local_model.encode(texts, normalize_embeddings=True)
                return embeddings.tolist()
            except Exception as e:
                print(f"Local model encoding failed: {e}. Falling back...")
                
        # Deterministic Mock Fallback (returns 1536 float values based on text hash)
        mock_embeddings = []
        for text in texts:
            # Seed based on text hash
            h = hashlib.sha256(text.encode('utf-8')).digest()
            np.random.seed(int.from_bytes(h[:4], 'big'))
            # Generate 1536 numbers between -1 and 1
            vec = np.random.uniform(-1.0, 1.0, 1536)
            # Normalize vector
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            mock_embeddings.append(vec.tolist())
            
        return mock_embeddings

embedding_service = EmbeddingService()

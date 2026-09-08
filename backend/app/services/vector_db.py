import uuid
import re
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models
from app.config import settings
from app.services.embedding_service import embedding_service


class QdrantService:
    def __init__(self):
        if settings.QDRANT_PATH:
            try:
                self.client = QdrantClient(path=settings.QDRANT_PATH)
            except Exception as e:
                print(f"Qdrant local storage locked ({e}). Falling back to in-memory Qdrant.")
                self.client = QdrantClient(":memory:")
        elif settings.QDRANT_HOST:
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY
            )
        else:
            self.client = QdrantClient(":memory:")

        self.collection_name = settings.QDRANT_COLLECTION
        self._initialized = False

    def ensure_collection(self, vector_size: int):
        """Creates collection if it doesn't already exist."""
        if self._initialized:
            return

        try:
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]

            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=rest_models.VectorParams(
                        size=vector_size,
                        distance=rest_models.Distance.COSINE
                    )
                )
                print(f"Created Qdrant collection: {self.collection_name} (size={vector_size})")
            self._initialized = True
        except Exception as e:
            print(f"Error checking/creating Qdrant collection: {e}")

    def index_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]], repository_id: str) -> List[str]:
        """
        Indexes chunks with their corresponding vectors into Qdrant.
        Stores rich metadata: repository_id, file_path, language, symbol_name, symbol_type,
        parent_symbol, start_line, end_line, relationships, and content.
        """
        if not chunks or not embeddings:
            return []

        vector_size = len(embeddings[0])
        self.ensure_collection(vector_size)

        points = []
        vector_ids = []

        for chunk, vector in zip(chunks, embeddings):
            vector_id = str(uuid.uuid4())
            vector_ids.append(vector_id)

            # Determine file path robustly
            file_path = chunk.get("file_path")
            if not file_path:
                cid = chunk.get("chunk_id", "")
                file_path = cid.split("_class_")[0].split("_func_")[0].split("_method_")[0].split("_module_")[0].split("_chunk_")[0]

            sym_type = chunk.get("symbol_type") or chunk.get("chunk_type") or "module"
            sym_name = chunk.get("symbol_name") or ""

            payload = {
                "repository_id": str(repository_id),
                "file_path": file_path,
                "language": chunk.get("language", ""),
                "symbol_name": sym_name,
                "symbol_type": sym_type,
                "chunk_type": sym_type,  # backwards compatibility
                "parent_symbol": chunk.get("parent_symbol"),
                "start_line": chunk.get("start_line", 1),
                "end_line": chunk.get("end_line", 1),
                "relationships": chunk.get("relationships", {}),
                "content": chunk["content"]
            }

            points.append(
                rest_models.PointStruct(
                    id=vector_id,
                    vector=vector,
                    payload=payload
                )
            )

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            return vector_ids
        except Exception as e:
            print(f"Failed to index points in Qdrant: {e}")
            return []

    def search_similar_chunks(
        self,
        query_text: str,
        repository_id: str,
        limit: int = 5,
        symbol_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Queries Qdrant for semantically and structurally relevant code chunks.
        Strictly isolates results to repository_id.
        Boosts structurally relevant symbols when symbol names match query tokens.
        """
        query_vector = embedding_service.get_embedding(query_text)
        vector_size = len(query_vector)
        self.ensure_collection(vector_size)

        filter_conditions = [
            rest_models.FieldCondition(
                key="repository_id",
                match=rest_models.MatchValue(value=str(repository_id))
            )
        ]

        if symbol_filter:
            filter_conditions.append(
                rest_models.FieldCondition(
                    key="symbol_name",
                    match=rest_models.MatchValue(value=symbol_filter)
                )
            )

        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=rest_models.Filter(must=filter_conditions),
                limit=limit * 2 if limit < 10 else limit
            )

            hits = []
            query_tokens = set(re.findall(r'\w+', query_text.lower()))

            for hit in results.points:
                payload = hit.payload or {}
                sym_name = (payload.get("symbol_name") or "").lower()
                file_name = (payload.get("file_path") or "").lower()

                # Structural relevance scoring boost
                score = hit.score
                if sym_name and sym_name in query_tokens:
                    score += 0.15
                if any(t in file_name for t in query_tokens if len(t) > 3):
                    score += 0.05

                hits.append({
                    "score": round(score, 4),
                    "content": payload.get("content", ""),
                    "file_path": payload.get("file_path", ""),
                    "symbol_name": payload.get("symbol_name", ""),
                    "symbol_type": payload.get("symbol_type") or payload.get("chunk_type", "module"),
                    "chunk_type": payload.get("chunk_type") or payload.get("symbol_type", "module"),
                    "parent_symbol": payload.get("parent_symbol"),
                    "language": payload.get("language", ""),
                    "start_line": payload.get("start_line", 1),
                    "end_line": payload.get("end_line", 1),
                    "relationships": payload.get("relationships", {})
                })

            # Sort by boosted score and return top matches
            hits.sort(key=lambda x: x["score"], reverse=True)
            return hits[:limit]
        except Exception as e:
            print(f"Error searching similarity in Qdrant: {e}")
            return []


qdrant_service = QdrantService()

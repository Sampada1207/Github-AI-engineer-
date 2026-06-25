import uuid
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models
from app.config import settings
from app.services.embedding_service import embedding_service

class QdrantService:
    def __init__(self):
        # Determine client setup based on configuration
        if settings.QDRANT_PATH:
            self.client = QdrantClient(path=settings.QDRANT_PATH)
        elif settings.QDRANT_HOST:
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY
            )
        else:
            # Fallback to memory
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
        Indexes a list of chunks with their corresponding vectors into Qdrant.
        Adds metadata fields like repository_id, path, start_line, end_line, and chunk_type.
        Returns a list of vector IDs generated.
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
            
            payload = {
                "repository_id": repository_id,
                "file_path": chunk.get("chunk_id", "").split("_class_")[0].split("_func_")[0].split("_module_")[0].split("_chunk_")[0],
                "content": chunk["content"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "chunk_type": chunk["chunk_type"]
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

    def search_similar_chunks(self, query_text: str, repository_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Queries the vector database for chunks similar to the query text.
        Filters searches by repository_id to prevent cross-repository matches.
        """
        query_vector = embedding_service.get_embedding(query_text)
        vector_size = len(query_vector)
        self.ensure_collection(vector_size)
        
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=rest_models.Filter(
                    must=[
                        rest_models.FieldCondition(
                            key="repository_id",
                            match=rest_models.MatchValue(value=repository_id)
                        )
                    ]
                ),
                limit=limit
            )
            
            hits = []
            for hit in results.points:
                hits.append({
                    "score": hit.score,
                    "content": hit.payload["content"],
                    "file_path": hit.payload["file_path"],
                    "start_line": hit.payload["start_line"],
                    "end_line": hit.payload["end_line"],
                    "chunk_type": hit.payload["chunk_type"]
                })
            return hits
        except Exception as e:
            print(f"Error searching similarity in Qdrant: {e}")
            return []

qdrant_service = QdrantService()

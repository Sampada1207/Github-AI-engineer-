import pytest
from app.utils.security import get_password_hash, verify_password, create_access_token, verify_access_token
from app.services.git_service import git_service
from app.services.parser_service import parser_service
from app.services.embedding_service import embedding_service
from app.services.vector_db import qdrant_service

def test_security_helpers():
    password = "secretpassword123"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

    # Token test
    subject = "user-12345"
    token = create_access_token(subject, role="admin")
    payload = verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == subject
    assert payload["role"] == "admin"

def test_git_language_detection():
    assert git_service.detect_language("main.py") == "Python"
    assert git_service.detect_language("utils.ts") == "TypeScript"
    assert git_service.detect_language("index.jsx") == "JavaScript React"
    assert git_service.detect_language("server.go") == "Go"
    assert git_service.detect_language("Dockerfile") == "Docker"
    assert git_service.detect_language("unknown.xyz") == "Unknown"

def test_parser_python():
    code = (
        "import os\n"
        "from sys import exit\n\n"
        "class CodeAnalyzer:\n"
        "    def __init__(self):\n"
        "        pass\n\n"
        "def main_process():\n"
        "    print('hello')\n"
    )
    result = parser_service.parse_file(code, "analyzer.py", "Python")
    
    assert any("os" in imp or "sys" in imp for imp in result["imports"])
    assert len(result["classes"]) == 1
    assert result["classes"][0]["name"] == "CodeAnalyzer"
    assert len(result["functions"]) == 2 # __init__ and main_process
    assert any(f["name"] == "main_process" for f in result["functions"])

def test_semantic_chunking():
    code = (
        "import math\n\n"
        "class MathHelper:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n\n"
        "def subtract(a, b):\n"
        "    return a - b\n"
    )
    parsed = parser_service.parse_file(code, "math_utils.py", "Python")
    chunks = parser_service.create_semantic_chunks(code, "math_utils.py", parsed)
    
    assert len(chunks) >= 2
    types = [ch["chunk_type"] for ch in chunks]
    assert "class" in types
    assert "function" in types

def test_embedding_generation():
    text = "Find functions calculating metrics in database files"
    vec = embedding_service.get_embedding(text)
    assert len(vec) in (1536, 1024, 384) # supports mock, bge, or openai dimensions
    assert isinstance(vec[0], float)

def test_qdrant_indexing_flow():
    # Setup test chunks
    chunks = [
        {
            "chunk_id": "test_file_func_dummy_1_4",
            "content": "def dummy_func():\n    return 42",
            "start_line": 1,
            "end_line": 2,
            "chunk_type": "function"
        }
    ]
    embeddings = [embedding_service.get_embedding(chunks[0]["content"])]
    repo_id = "test-repo-uuid-999"
    
    # Connects to disk or memory client
    vector_ids = qdrant_service.index_chunks(chunks, embeddings, repo_id)
    assert len(vector_ids) == 1
    
    # Query test
    search_results = qdrant_service.search_similar_chunks("dummy_func", repo_id, limit=1)
    assert len(search_results) == 1
    assert search_results[0]["chunk_type"] == "function"

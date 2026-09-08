import pytest
from app.utils.security import get_password_hash, verify_password, create_access_token, verify_access_token
from app.services.git_service import git_service
from app.services.parser_service import parser_service
from app.services.embedding_service import embedding_service
from app.services.vector_db import qdrant_service
from app.services.analysis_service import analysis_service
from app.agents.tools import search_codebase, list_code_symbols, get_repository_overview


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


def test_symbol_and_relationship_extraction_python():
    code = (
        "import os\n"
        "from typing import List\n\n"
        "MAX_RETRIES = 3\n\n"
        "class BaseWorker:\n"
        "    def run(self):\n"
        "        pass\n\n"
        "class CodeAnalyzer(BaseWorker):\n"
        "    def __init__(self, name: str):\n"
        "        self.name = name\n\n"
        "    def analyze(self):\n"
        "        self.run()\n"
        "        main_process()\n\n"
        "def main_process():\n"
        "    print('starting')\n"
    )
    result = parser_service.parse_file(code, "analyzer.py", "Python")

    # Imports
    assert any("os" in imp for imp in result["imports"])
    assert any("typing" in imp for imp in result["imports"])
    assert "os" in result["dependencies"]

    # Variables
    assert len(result["variables"]) >= 1
    assert result["variables"][0]["name"] == "MAX_RETRIES"
    assert result["variables"][0]["type"] == "constant"

    # Classes & Inheritance
    assert len(result["classes"]) == 2
    analyzer_cls = next(c for c in result["classes"] if c["name"] == "CodeAnalyzer")
    assert analyzer_cls["bases"] == ["BaseWorker"]
    assert "analyze" in analyzer_cls["methods"]

    # Methods & Parent Symbol Containment
    methods = [f for f in result["functions"] if f.get("parent_symbol") == "CodeAnalyzer"]
    assert len(methods) >= 2
    analyze_method = next(m for m in methods if m["name"] == "analyze")
    assert "run" in analyze_method["calls"] or "main_process" in analyze_method["calls"]

    # Top-level Functions
    top_funcs = [f for f in result["functions"] if f.get("parent_symbol") is None]
    assert any(f["name"] == "main_process" for f in top_funcs)

    # Relationships
    rel = result["relationships"]
    assert any(inh["class"] == "CodeAnalyzer" and "BaseWorker" in inh["bases"] for inh in rel["inheritance"])
    assert any(cnt["parent"] == "CodeAnalyzer" and cnt["child"] == "analyze" for cnt in rel["containment"])


def test_symbol_extraction_js_ts():
    code = (
        "import { useEffect } from 'react';\n"
        "import axios from 'axios';\n\n"
        "export class ApiClient extends BaseClient {\n"
        "    fetchData(endpoint) {\n"
        "        return axios.get(endpoint);\n"
        "    }\n"
        "}\n\n"
        "export function renderHeader(title) {\n"
        "    return title;\n"
        "}\n"
    )
    result = parser_service.parse_file(code, "client.ts", "TypeScript")

    assert any("axios" in dep for dep in result["dependencies"])
    assert len(result["classes"]) >= 1
    assert result["classes"][0]["name"] == "ApiClient"
    assert len(result["functions"]) >= 1
    assert any(f["name"] in ("fetchData", "renderHeader") for f in result["functions"])


def test_smart_chunking_with_metadata():
    code = (
        "import math\n\n"
        "class MathHelper:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n\n"
        "def subtract(a, b):\n"
        "    return a - b\n"
    )
    parsed = parser_service.parse_file(code, "math_utils.py", "Python")
    chunks = parser_service.create_semantic_chunks(code, "math_utils.py", parsed, language="Python")

    assert len(chunks) >= 2
    types = [ch["symbol_type"] for ch in chunks]
    assert "class" in types or "method" in types
    assert "function" in types

    # Check that rich metadata is attached
    for ch in chunks:
        assert "symbol_name" in ch
        assert "symbol_type" in ch
        assert "file_path" in ch
        assert ch["language"] == "Python"
        assert "start_line" in ch
        assert "end_line" in ch


def test_embedding_generation():
    text = "Find functions calculating metrics in database files"
    vec = embedding_service.get_embedding(text)
    assert len(vec) in (1536, 1024, 384)
    assert isinstance(vec[0], float)


def test_qdrant_rich_metadata_and_structural_search():
    chunks = [
        {
            "chunk_id": "service_py_class_AuthService_1_20",
            "file_path": "services/auth_service.py",
            "language": "Python",
            "symbol_name": "AuthService",
            "symbol_type": "class",
            "parent_symbol": None,
            "content": "class AuthService:\n    def login(self, username, password):\n        return True",
            "start_line": 1,
            "end_line": 20,
            "relationships": {"methods": ["login"]}
        },
        {
            "chunk_id": "service_py_method_login_5_15",
            "file_path": "services/auth_service.py",
            "language": "Python",
            "symbol_name": "login",
            "symbol_type": "method",
            "parent_symbol": "AuthService",
            "content": "def login(self, username, password):\n    return verify_password(password)",
            "start_line": 5,
            "end_line": 15,
            "relationships": {"calls": ["verify_password"]}
        }
    ]
    embeddings = [embedding_service.get_embedding(ch["content"]) for ch in chunks]
    repo_id = "test-repo-uuid-phase2"

    # Index with enriched metadata
    vector_ids = qdrant_service.index_chunks(chunks, embeddings, repo_id)
    assert len(vector_ids) == 2

    # Query with structural search
    search_results = qdrant_service.search_similar_chunks("login function authentication", repo_id, limit=2)
    assert len(search_results) >= 1
    assert search_results[0]["file_path"] == "services/auth_service.py"
    assert search_results[0]["symbol_name"] in ("AuthService", "login")

    # Verify repository isolation
    other_repo_results = qdrant_service.search_similar_chunks("login", "non-existent-repo-999", limit=2)
    assert len(other_repo_results) == 0


def test_repository_summary_generation():
    files_data = [
        {
            "path": "app/main.py",
            "name": "main.py",
            "language": "Python",
            "size": 500,
            "content": "from app.services import UserService\n\ndef main():\n    app = UserService()\n    app.start()\n"
        },
        {
            "path": "app/services/user_service.py",
            "name": "user_service.py",
            "language": "Python",
            "size": 800,
            "content": "class UserService:\n    def start(self):\n        print('running')\n"
        }
    ]
    summary = analysis_service.generate_repository_summary(files_data)

    assert summary["total_files"] == 2
    assert summary["total_lines"] > 0
    assert "Python" in summary["languages"]
    assert any(kf["path"] == "app/main.py" for kf in summary["key_files"])
    assert any(c["name"] == "UserService" for c in summary["classes"])
    assert "## Repository Architecture Overview" in summary["summary_text"]

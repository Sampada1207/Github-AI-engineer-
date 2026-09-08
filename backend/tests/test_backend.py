import pytest
from app.utils.security import get_password_hash, verify_password, create_access_token, verify_access_token
from app.services.git_service import git_service
from app.services.parser_service import parser_service
from app.services.embedding_service import embedding_service
from app.services.vector_db import qdrant_service
from app.services.analysis_service import analysis_service
from app.services.knowledge_graph import knowledge_graph_service, GraphNode, GraphEdge
from app.services.hybrid_rag import hybrid_rag_service
from app.agents.tools import (
    search_codebase,
    list_code_symbols,
    get_repository_overview,
    get_symbol_relationships,
    find_symbol_usages,
    get_file_dependencies,
    get_impact_analysis
)


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


# ================= PHASE 3: KNOWLEDGE GRAPH & HYBRID RAG TESTS =================

def test_knowledge_graph_construction_and_isolation():
    repo_id = "repo-kg-test-101"
    files_data = [
        {
            "path": "services/auth.py",
            "name": "auth.py",
            "language": "Python",
            "size": 600,
            "content": (
                "class BaseAuth:\n"
                "    pass\n\n"
                "class AuthService(BaseAuth):\n"
                "    def authenticate(self, token):\n"
                "        return validate_token(token)\n\n"
                "def validate_token(token):\n"
                "    return True\n"
            )
        },
        {
            "path": "routes/login.py",
            "name": "login.py",
            "language": "Python",
            "size": 400,
            "content": (
                "from services.auth import AuthService\n\n"
                "def login_route():\n"
                "    auth = AuthService()\n"
                "    return auth.authenticate('sample')\n"
            )
        }
    ]

    # Build Graph
    kg = knowledge_graph_service.build_graph_from_repository(repo_id, files_data)
    assert len(kg.nodes) >= 6
    assert len(kg.out_edges) > 0

    # Test Repository Isolation
    other_kg = knowledge_graph_service.get_graph("unrelated-repo-999")
    assert len(other_kg.nodes) == 0


def test_knowledge_graph_relationships_and_usages():
    repo_id = "repo-kg-rel-usages-202"
    files_data = [
        {
            "path": "services/auth.py",
            "name": "auth.py",
            "language": "Python",
            "size": 600,
            "content": (
                "class BaseAuth:\n"
                "    pass\n\n"
                "class AuthService(BaseAuth):\n"
                "    def authenticate(self, token):\n"
                "        return validate_token(token)\n\n"
                "def validate_token(token):\n"
                "    return True\n"
            )
        },
        {
            "path": "routes/login.py",
            "name": "login.py",
            "language": "Python",
            "size": 400,
            "content": (
                "from services.auth import AuthService\n\n"
                "def login_route():\n"
                "    auth = AuthService()\n"
                "    return auth.authenticate('sample')\n"
            )
        }
    ]

    # Ensure graph is built deterministically for this test
    knowledge_graph_service.build_graph_from_repository(repo_id, files_data)
    
    # 1. Symbol relationships for AuthService
    auth_rel = knowledge_graph_service.get_symbol_relationships("AuthService", repo_id)
    assert auth_rel["found"] is True
    match = auth_rel["matches"][0]
    assert match["name"] == "AuthService"
    assert "BaseAuth" in match["extends"]
    assert any("authenticate" in c for c in match["contains"])

    # 2. Usages of authenticate function
    usages = knowledge_graph_service.find_symbol_usages("validate_token", repo_id)
    assert usages["total_usages"] >= 1
    assert any(u["caller_name"] == "authenticate" for u in usages["usages"])



def test_knowledge_graph_file_dependencies_and_impact():
    repo_id = "repo-kg-test-101"

    # 1. File dependencies for routes/login.py
    login_deps = knowledge_graph_service.get_file_dependencies("routes/login.py", repo_id)
    assert login_deps["found"] is True
    assert any("services/auth.py" in imp for imp in login_deps["internal_imports"])

    # 2. Impact analysis if validate_token or AuthService changes
    impact = knowledge_graph_service.get_impact_analysis("validate_token", repo_id)
    assert impact["affected_symbols_count"] >= 1
    assert any("authenticate" in sym for sym in impact["affected_symbols"])


def test_hybrid_rag_retrieval_and_context_building():
    repo_id = "repo-kg-test-101"

    # Index chunks in Qdrant for this repo so vector search has targets
    chunks = [
        {
            "chunk_id": "auth_py_class_AuthService_1_10",
            "file_path": "services/auth.py",
            "language": "Python",
            "symbol_name": "AuthService",
            "symbol_type": "class",
            "parent_symbol": None,
            "content": "class AuthService(BaseAuth):\n    def authenticate(self, token):\n        return validate_token(token)",
            "start_line": 1,
            "end_line": 10,
            "relationships": {"bases": ["BaseAuth"], "methods": ["authenticate"]}
        }
    ]
    embeddings = [embedding_service.get_embedding(chunks[0]["content"])]
    qdrant_service.index_chunks(chunks, embeddings, repo_id)

    # Perform Hybrid Retrieval
    hybrid_result = hybrid_rag_service.retrieve_hybrid_context("How does authenticate work with AuthService?", repo_id, limit=3)
    assert "context" in hybrid_result
    assert len(hybrid_result["citations"]) >= 1
    assert "Relevant Code Snippets" in hybrid_result["context"]
    assert "Structural Code Knowledge Graph" in hybrid_result["context"]


def test_agent_graph_tools_execution():
    repo_id = "repo-kg-test-101"

    # 1. get_symbol_relationships tool
    rel_out = get_symbol_relationships.invoke({"symbol_name": "AuthService", "repository_id": repo_id})
    assert "Knowledge Graph Relationships for `AuthService`" in rel_out
    assert "BaseAuth" in rel_out

    # 2. find_symbol_usages tool
    usage_out = find_symbol_usages.invoke({"symbol_name": "validate_token", "repository_id": repo_id})
    assert "Usages of `validate_token`" in usage_out

    # 3. get_file_dependencies tool
    dep_out = get_file_dependencies.invoke({"file_path": "routes/login.py", "repository_id": repo_id})
    assert "Dependency Graph for `routes/login.py`" in dep_out
    assert "services/auth.py" in dep_out

    # 4. get_impact_analysis tool
    impact_out = get_impact_analysis.invoke({"target": "validate_token", "repository_id": repo_id})
    assert "Impact Analysis for `validate_token`" in impact_out
    assert "authenticate" in impact_out

    # 5. search_codebase tool with hybrid context
    search_out = search_codebase.invoke({"query": "AuthService authenticate", "repository_id": repo_id})
    assert "Relevant Code Snippets" in search_out or "AuthService" in search_out


# ================= PHASE 4: AI CODE REVIEW & IMPACT ANALYSIS TESTS =================

def test_ai_code_review_service_and_findings_structure():
    from app.services.review_service import ai_code_review_service
    repo_id = "repo-kg-test-101"

    code_with_bugs = (
        "import os\n"
        "SECRET_KEY = 'super_secret_password_12345'\n"
        "def unsafe_exec(user_input):\n"
        "    eval(user_input)\n"
        "def bad_error_handling():\n"
        "    try:\n"
        "        do_something()\n"
        "    except:\n"
        "        pass\n"
    )

    review_res = ai_code_review_service.review_codebase(
        repository_id=repo_id,
        file_path="app/vulnerable.py",
        code_snippet=code_with_bugs
    )

    assert review_res["repository_id"] == repo_id
    assert "overall_summary" in review_res
    assert "impact_analysis" in review_res
    
    findings = review_res["findings"]
    assert len(findings) >= 3

    # Check finding structures
    categories = [f["category"] for f in findings]
    severities = [f["severity"] for f in findings]

    assert "Security" in categories
    assert "Error Handling" in categories
    assert "Critical" in severities or "High" in severities

    for f in findings:
        assert "severity" in f
        assert "category" in f
        assert "file" in f
        assert "explanation" in f
        assert "suggested_fix" in f


def test_enhanced_impact_analysis_fields():
    repo_id = "repo-kg-test-101"
    impact = knowledge_graph_service.get_impact_analysis("validate_token", repo_id)

    assert impact["target"] == "validate_token"
    assert "impact_risk" in impact
    assert "blast_radius_score" in impact
    assert isinstance(impact["blast_radius_score"], (int, float))
    assert "directly_affected_symbols" in impact
    assert "dependent_files" in impact
    assert "callers" in impact
    assert "dependencies" in impact
    assert "limitations_notice" in impact
    assert "Static graph traversal analysis" in impact["limitations_notice"]


def test_review_code_agent_tool():
    from app.agents.tools import review_code
    repo_id = "repo-kg-test-101"

    tool_out = review_code.invoke({
        "repository_id": repo_id,
        "file_path": "services/auth.py",
        "symbol_name": "AuthService"
    })

    assert "AI Code Review Summary" in tool_out
    assert "Detailed Findings" in tool_out


# ================= PHASE 5: SECURITY, EVALUATION & RELIABILITY TESTS =================

def test_git_url_security_validation():
    # Valid HTTPS & SSH URLs
    assert git_service.validate_git_url("https://github.com/octocat/Spoon-Knife.git") == "https://github.com/octocat/Spoon-Knife.git"
    assert git_service.validate_git_url("git@github.com:octocat/Spoon-Knife.git") == "git@github.com:octocat/Spoon-Knife.git"

    # Reject local file URLs and command injection strings
    with pytest.raises(ValueError, match="Only HTTP\(S\) and git remote URLs are supported"):
        git_service.validate_git_url("file:///etc/passwd")

    with pytest.raises(ValueError, match="Repository URL contains invalid characters"):
        git_service.validate_git_url("https://github.com/test.git; rm -rf /")

    with pytest.raises(ValueError, match="Embedded credentials in repository URLs are not allowed"):
        git_service.validate_git_url("https://user:password@github.com/test.git")


def test_path_traversal_rejection_in_tools():
    from app.agents.tools import read_file_content
    repo_id = "repo-kg-test-101"

    res1 = read_file_content.invoke({"file_path": "../../../etc/passwd", "repository_id": repo_id})
    assert "Path traversal or invalid file path detected" in res1

    res2 = read_file_content.invoke({"file_path": "/etc/shadow", "repository_id": repo_id})
    assert "Path traversal or invalid file path detected" in res2


def test_ai_evaluation_suite_benchmark():
    from app.evaluation.eval_suite import ai_evaluation_suite
    repo_id = "repo-kg-test-101"

    eval_results = ai_evaluation_suite.run_full_evaluation(repository_id=repo_id)

    assert "overall_evaluation_score" in eval_results
    assert eval_results["overall_evaluation_score"] >= 80.0
    assert eval_results["status"] == "PASSED"
    assert len(eval_results["evaluations"]) == 3



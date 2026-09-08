import re
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.services.hybrid_rag import hybrid_rag_service
from app.services.knowledge_graph import knowledge_graph_service
from app.services.analysis_service import analysis_service
from app.services.parser_service import parser_service


class AICodeReviewService:
    """
    Repository-Aware AI Code Review Engine combining static AST analysis,
    Hybrid RAG semantic context, Knowledge Graph impact analysis, and structured findings.
    """

    def review_codebase(
        self,
        repository_id: str,
        file_path: Optional[str] = None,
        symbol_name: Optional[str] = None,
        code_snippet: Optional[str] = None,
        files_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Executes a repository-aware AI Code Review for a target file, symbol, code snippet,
        or entire repository workspace.
        """
        repo_id = str(repository_id)
        findings: List[Dict[str, Any]] = []

        # Target label identification
        target_label = symbol_name or file_path or "Entire Repository Workspace"

        # 1. Gather Code Content
        target_code = code_snippet or ""
        target_file_path = file_path or "code_snippet"

        if not target_code and files_data:
            if file_path:
                for f in files_data:
                    if f["path"] == file_path or os.path.basename(f["path"]) == os.path.basename(file_path):
                        target_code = f.get("content", "")
                        target_file_path = f["path"]
                        break
            elif symbol_name:
                # Search symbol across files
                for f in files_data:
                    if symbol_name in (f.get("content") or ""):
                        target_code = f.get("content", "")
                        target_file_path = f["path"]
                        break

        # Fallback to database files if files_data not directly passed
        if not target_code and file_path:
            try:
                from app.database import SessionLocal
                from app.models.models import RepositoryFile
                db = SessionLocal()
                try:
                    db_file = db.query(RepositoryFile).filter(
                        RepositoryFile.repository_id == repo_id,
                        RepositoryFile.path == file_path
                    ).first()
                    if db_file:
                        target_code = db_file.content
                        target_file_path = db_file.path
                finally:
                    db.close()
            except Exception as e:
                print(f"Could not load file from DB for review: {e}")

        # 2. Perform Impact Analysis
        impact = knowledge_graph_service.get_impact_analysis(
            symbol_name or file_path or repo_id, repo_id
        )

        # 3. Perform Hybrid RAG Context Lookup
        query_topic = f"{symbol_name or file_path or 'code review'} security bugs error handling performance"
        hybrid_context = hybrid_rag_service.retrieve_hybrid_context(query_topic, repo_id, limit=3)

        # 4. Perform Structured Audit Rules Scan
        if target_code:
            self._audit_code_content(target_code, target_file_path, symbol_name, findings)
        elif files_data:
            for f in files_data[:10]:
                self._audit_code_content(f.get("content", ""), f["path"], None, findings)

        # 5. Build Overall Summary
        critical_count = sum(1 for f in findings if f["severity"] == "Critical")
        high_count = sum(1 for f in findings if f["severity"] == "High")
        medium_count = sum(1 for f in findings if f["severity"] == "Medium")
        
        status_health = "Excellent" if not findings else "Action Required" if (critical_count + high_count) > 0 else "Good"

        overall_summary = (
            f"### AI Code Review Summary for `{target_label}`\n\n"
            f"- **Repository Status**: {status_health}\n"
            f"- **Identified Findings**: {len(findings)} ({critical_count} Critical, {high_count} High, {medium_count} Medium)\n"
            f"- **Impact Risk**: {impact['impact_risk']} (Blast Radius Score: {impact['blast_radius_score']}/100)\n"
            f"- **Potentially Affected Callers/Files**: {impact['affected_symbols_count']} symbols, {impact['affected_files_count']} files\n\n"
            f"**Structural Context**: {hybrid_context.get('graph_relations_count', 0)} knowledge graph relations analyzed.\n\n"
            f"_{impact.get('limitations_notice', '')}_"
        )

        return {
            "repository_id": repo_id,
            "target": target_label,
            "overall_summary": overall_summary,
            "findings": findings,
            "impact_analysis": impact,
            "created_at": datetime.utcnow()
        }

    def _audit_code_content(
        self,
        code: str,
        file_path: str,
        symbol_name: Optional[str],
        findings: List[Dict[str, Any]]
    ):
        """Rule-based code review scanning grounded in actual code evidence."""
        lines = code.splitlines()

        for idx, line in enumerate(lines):
            line_num = idx + 1
            stripped = line.strip()

            # A. Security Scan: Hardcoded secrets
            if re.search(r'(?:api_key|secret|password|token)\s*[:=]\s*[\'"][A-Za-z0-9_\-\.\=\+]{8,}[\'"]', line, re.IGNORECASE) and not line.startswith(("import", "from")):
                findings.append({
                    "severity": "Critical",
                    "category": "Security",
                    "file": file_path,
                    "line": line_num,
                    "explanation": f"Hardcoded credential or secret key exposed inline in line {line_num}.",
                    "suggested_fix": (
                        "# Move credentials to environment variables:\n"
                        "import os\n"
                        "SECRET_KEY = os.getenv('SECRET_KEY')"
                    )
                })

            # B. Security Scan: Code execution vulnerability
            if "eval(" in stripped or "exec(" in stripped or "shell=True" in stripped:
                findings.append({
                    "severity": "Critical",
                    "category": "Security",
                    "file": file_path,
                    "line": line_num,
                    "explanation": f"Potentially unsafe dynamic execution or subprocess command with shell=True on line {line_num}.",
                    "suggested_fix": (
                        "# Avoid eval/exec or shell=True; use structured argument arrays:\n"
                        "subprocess.run(['command', 'arg1', 'arg2'], check=True)"
                    )
                })

            # C. Bugs / Error Handling: Bare excepts or empty catch blocks
            if stripped in ("except:", "except Exception:", "catch (e) {}", "catch (e) { }"):
                findings.append({
                    "severity": "High",
                    "category": "Error Handling",
                    "file": file_path,
                    "line": line_num,
                    "explanation": f"Swallowed exception or bare try-except block on line {line_num} masks unexpected runtime failures.",
                    "suggested_fix": (
                        "try:\n"
                        "    # operation\n"
                        "except SpecificException as err:\n"
                        "    logger.error(f'Operation failed: {err}')\n"
                        "    raise"
                    )
                })

            # D. Performance: Database commit inside loops
            if ".commit()" in line and any(k in code for k in ("for ", "while ")):
                findings.append({
                    "severity": "Medium",
                    "category": "Performance",
                    "file": file_path,
                    "line": line_num,
                    "explanation": f"Database commit call inside loop construct at line {line_num} incurs severe disk I/O overhead.",
                    "suggested_fix": (
                        "# Perform batch operations and commit once outside the loop:\n"
                        "# ... populate objects ...\n"
                        "db.commit()"
                    )
                })

            # E. Bad Practices: Print statements in production code
            if stripped.startswith("print(") and not file_path.endswith("test_backend.py"):
                findings.append({
                    "severity": "Low",
                    "category": "Bad Practices",
                    "file": file_path,
                    "line": line_num,
                    "explanation": f"Raw `print()` call found at line {line_num}. Use a structured logger instead.",
                    "suggested_fix": (
                        "import logging\n"
                        "logger = logging.getLogger(__name__)\n"
                        "logger.info('Structured log message')"
                    )
                })

            # F. Maintainability: Extremely long line
            if len(line) > 140:
                findings.append({
                    "severity": "Low",
                    "category": "Maintainability",
                    "file": file_path,
                    "line": line_num,
                    "explanation": f"Line exceeds 140 characters ({len(line)} chars). High complexity degrades code scannability.",
                    "suggested_fix": "# Refactor statement onto multiple logical lines."
                })


ai_code_review_service = AICodeReviewService()

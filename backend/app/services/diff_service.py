import os
import re
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from app.services.git_service import git_service
from app.services.knowledge_graph import knowledge_graph_service
from app.services.hybrid_rag import hybrid_rag_service


class GitDiffService:
    """
    Service to execute safe Git diff extraction, change-aware Knowledge Graph analysis,
    and AI-assisted diff reviews.
    """

    def validate_revision(self, rev: str) -> str:
        """
        Validates Git revision syntax to prevent argument injection or malicious input.
        Rejects revisions with shell metacharacters or leading option flags.
        """
        if not rev or not isinstance(rev, str):
            raise ValueError("Revision identifier must be a non-empty string.")
        
        rev = rev.strip()
        if not rev:
            raise ValueError("Revision identifier cannot be empty.")
            
        # Reject leading dash to avoid argument injection (e.g. --exec, -o)
        if rev.startswith("-"):
            raise ValueError("Invalid revision identifier format.")
            
        # Reject shell metacharacters and suspicious control characters
        invalid_chars = [";", "|", "&", "$", "`", "\n", "\r", "\x00", " ", "\t", "<", ">", "(", ")"]
        if any(c in rev for c in invalid_chars):
            raise ValueError("Revision identifier contains invalid or unsafe characters.")
            
        # Match safe git ref formats (e.g., main, HEAD~1, origin/main, commit hashes, v1.0.0)
        if not re.match(r"^[a-zA-Z0-9_.\-/~^@{}]+$", rev):
            raise ValueError("Revision identifier contains unsupported characters.")
            
        return rev

    def parse_diff_text(self, diff_text: str) -> List[Dict[str, Any]]:
        """
        Parses unified diff format text into structured file change items,
        hunks, and changed symbols.
        """
        if not diff_text or not diff_text.strip():
            return []

        files: List[Dict[str, Any]] = []
        current_file: Optional[Dict[str, Any]] = None
        current_hunk: Optional[Dict[str, Any]] = None

        lines = diff_text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect file headers
            if line.startswith("diff --git "):
                if current_file:
                    if current_hunk:
                        current_file["hunks"].append(current_hunk)
                        current_hunk = None
                    files.append(current_file)

                # Extract file paths e.g. diff --git a/file.py b/file.py
                parts = line.split(" ")
                old_path = parts[2][2:] if len(parts) > 2 and parts[2].startswith("a/") else ""
                new_path = parts[3][2:] if len(parts) > 3 and parts[3].startswith("b/") else old_path

                current_file = {
                    "path": new_path or old_path or "unknown",
                    "change_type": "modified",
                    "additions": 0,
                    "deletions": 0,
                    "changed_symbols": set(),
                    "hunks": []
                }
                i += 1
                continue

            if current_file:
                if line.startswith("new file mode"):
                    current_file["change_type"] = "added"
                elif line.startswith("deleted file mode"):
                    current_file["change_type"] = "deleted"
                elif line.startswith("--- a/"):
                    pass
                elif line.startswith("+++ b/"):
                    file_path = line[6:].strip()
                    if file_path and file_path != "/dev/null":
                        current_file["path"] = file_path
                elif line.startswith("@@ "):
                    if current_hunk:
                        current_file["hunks"].append(current_hunk)

                    # Parse hunk header e.g. @@ -10,5 +12,7 @@ def my_func():
                    hunk_header = line
                    m = re.match(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)", line)
                    old_start = int(m.group(1)) if m else 0
                    new_start = int(m.group(3)) if m else 0

                    # Check for symbol in hunk header
                    header_context = m.group(5) if m else ""
                    symbol_match = re.search(r'(?:def|class|function|const|let|var|type|interface)\s+([A-Za-z0-9_]+)', header_context)
                    if symbol_match:
                        current_file["changed_symbols"].add(symbol_match.group(1))

                    current_hunk = {
                        "header": hunk_header,
                        "old_start": old_start,
                        "new_start": new_start,
                        "lines": []
                    }
                elif current_hunk is not None:
                    current_hunk["lines"].append(line)

                    if line.startswith("+") and not line.startswith("+++"):
                        current_file["additions"] += 1
                        # Detect changed symbols in added lines
                        sym = self._extract_symbol_from_line(line[1:])
                        if sym:
                            current_file["changed_symbols"].add(sym)
                    elif line.startswith("-") and not line.startswith("---"):
                        current_file["deletions"] += 1
                        sym = self._extract_symbol_from_line(line[1:])
                        if sym:
                            current_file["changed_symbols"].add(sym)

            i += 1

        if current_file:
            if current_hunk:
                current_file["hunks"].append(current_hunk)
            files.append(current_file)

        # Format output list & set changed_symbols to sorted list
        res = []
        for f in files:
            res.append({
                "path": f["path"],
                "change_type": f["change_type"],
                "additions": f["additions"],
                "deletions": f["deletions"],
                "changed_symbols": sorted(list(f["changed_symbols"])),
                "hunks": f["hunks"]
            })
        return res

    def _extract_symbol_from_line(self, line_text: str) -> Optional[str]:
        """Extracts class, function, or method symbol names from a code line if present."""
        stripped = line_text.strip()
        # Python/JS/TS/Go/Java/C++ symbol declarations
        match = re.search(r'\b(?:def|class|function|interface|type|struct)\s+([A-Za-z_][A-Za-z0-9_]*)', stripped)
        if match:
            return match.group(1)

        # JS/TS const/let/var function assignments
        js_match = re.search(r'\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_]+)\s*=>', stripped)
        if js_match:
            return js_match.group(1)

        return None

    def get_repository_diff(
        self,
        repo_id: str,
        base_revision: str = "main",
        target_revision: str = "HEAD",
        diff_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves Git diff between two revisions or processes a raw diff_text payload.
        Returns structured DiffParseResponse dictionary.
        """
        valid_base = self.validate_revision(base_revision)
        valid_target = self.validate_revision(target_revision)

        raw_diff = diff_text or ""
        repo_path = git_service.repo_storage_path(repo_id)

        if not raw_diff and os.path.exists(repo_path):
            try:
                # Check if it's a git repo
                is_git = subprocess.run(
                    ["git", "rev-parse", "--is-inside-work-tree"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=False
                )
                if is_git.returncode == 0:
                    # Run safe subprocess git diff
                    cmd = ["git", "diff", f"{valid_base}...{valid_target}"]
                    result = subprocess.run(
                        cmd,
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    if result.returncode == 0:
                        raw_diff = result.stdout
                    else:
                        # Fallback to direct revision comparison if triple dot failed
                        cmd_fallback = ["git", "diff", valid_base, valid_target]
                        fb_res = subprocess.run(
                            cmd_fallback,
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        if fb_res.returncode == 0:
                            raw_diff = fb_res.stdout
            except Exception as e:
                print(f"Error executing git diff: {e}")

        parsed_files = self.parse_diff_text(raw_diff)

        total_files = len(parsed_files)
        total_adds = sum(f["additions"] for f in parsed_files)
        total_dels = sum(f["deletions"] for f in parsed_files)

        return {
            "repository_id": str(repo_id),
            "base_revision": valid_base,
            "target_revision": valid_target,
            "total_files_changed": total_files,
            "total_additions": total_adds,
            "total_deletions": total_dels,
            "files": parsed_files,
            "raw_diff": raw_diff
        }

    def analyze_diff_impact(
        self,
        repo_id: str,
        base_revision: str = "main",
        target_revision: str = "HEAD",
        diff_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Correlates changed files & changed symbols with the Knowledge Graph
        and Hybrid RAG to perform change-aware impact analysis.
        """
        diff_data = self.get_repository_diff(repo_id, base_revision, target_revision, diff_text)
        files = diff_data["files"]

        all_changed_symbols: List[str] = []
        all_changed_files: List[str] = [f["path"] for f in files]

        for f in files:
            all_changed_symbols.extend(f["changed_symbols"])
        all_changed_symbols = sorted(list(set(all_changed_symbols)))

        # Run Knowledge Graph impact analysis for changed symbols or files
        impact_target = all_changed_symbols[0] if all_changed_symbols else (all_changed_files[0] if all_changed_files else str(repo_id))
        kg_impact = knowledge_graph_service.get_impact_analysis(impact_target, repo_id)

        # Retrieve Hybrid RAG context for changed symbols/files
        topic_query = " ".join(all_changed_symbols[:5] + all_changed_files[:3]) or "diff code changes"
        hybrid_context = hybrid_rag_service.retrieve_hybrid_context(topic_query, repo_id, limit=3)

        return {
            "repository_id": str(repo_id),
            "base_revision": diff_data["base_revision"],
            "target_revision": diff_data["target_revision"],
            "total_files_changed": diff_data["total_files_changed"],
            "total_additions": diff_data["total_additions"],
            "total_deletions": diff_data["total_deletions"],
            "changed_files": all_changed_files,
            "changed_symbols": all_changed_symbols,
            "files": files,
            "raw_diff": diff_data.get("raw_diff", ""),
            "impact_analysis": kg_impact,
            "rag_context": hybrid_context
        }

    def review_diff(
        self,
        repo_id: str,
        base_revision: str = "main",
        target_revision: str = "HEAD",
        diff_text: Optional[str] = None,
        files_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        AI Diff Review Engine:
        Evaluates diff changes using changed code, surrounding repo context,
        Hybrid RAG, and Knowledge Graph relationships.
        Distinguishes issues in changed code, issues exposed by changes, and downstream impact.
        """
        analysis = self.analyze_diff_impact(repo_id, base_revision, target_revision, diff_text)
        files = analysis["files"]
        kg_impact = analysis["impact_analysis"]
        changed_symbols = analysis["changed_symbols"]

        findings: List[Dict[str, Any]] = []

        for f in files:
            file_path = f["path"]
            hunks = f["hunks"]

            for hunk in hunks:
                hunk_lines = hunk.get("lines", [])
                hunk_text = "\n".join(hunk_lines)

                # A. Security Scan on added diff lines
                for line_idx, line in enumerate(hunk_lines):
                    if line.startswith("+") and not line.startswith("+++"):
                        code_line = line[1:].strip()
                        line_num = hunk.get("new_start", 1) + line_idx

                        # Secret detection
                        if re.search(r'(?:api_key|secret|password|token)\s*[:=]\s*[\'"][A-Za-z0-9_\-\.\=\+]{8,}[\'"]', code_line, re.IGNORECASE) and not code_line.startswith(("import", "from")):
                            findings.append({
                                "severity": "Critical",
                                "category": "Security",
                                "file": file_path,
                                "line": line_num,
                                "explanation": f"Hardcoded secret key exposed in diff change on line {line_num}.",
                                "suggested_fix": "Use environment variables (os.getenv) instead of inline API keys.",
                                "finding_type": "issue in changed code"
                            })

                        # Command injection / unsafe exec
                        if "eval(" in code_line or "exec(" in code_line or "shell=True" in code_line:
                            findings.append({
                                "severity": "Critical",
                                "category": "Security",
                                "file": file_path,
                                "line": line_num,
                                "explanation": f"Unsafe execution pattern detected in change on line {line_num}.",
                                "suggested_fix": "Avoid shell=True or dynamic code evaluation; use safe parameterized execution.",
                                "finding_type": "issue in changed code"
                            })

                        # Bare except swallowing
                        if re.match(r"^except\s*:", code_line):
                            findings.append({
                                "severity": "Medium",
                                "category": "Error Handling",
                                "file": file_path,
                                "line": line_num,
                                "explanation": "Bare except clause added, which swallows unexpected exceptions.",
                                "suggested_fix": "Catch specific exception types (e.g. except Exception as e:) and log appropriately.",
                                "finding_type": "issue in changed code"
                            })

            # B. Downstream & Exposed Issues correlation
            if f["change_type"] == "modified" and f["deletions"] > 0 and f["changed_symbols"]:
                for sym in f["changed_symbols"]:
                    if sym in kg_impact.get("affected_symbols", []):
                        findings.append({
                            "severity": "High",
                            "category": "Maintainability",
                            "file": file_path,
                            "line": f"Symbol: {sym}",
                            "explanation": f"Modification of symbol `{sym}` affects {kg_impact.get('affected_symbols_count', 0)} downstream callers.",
                            "suggested_fix": f"Verify all callers of `{sym}` match the updated function signature and contract.",
                            "finding_type": "potential downstream impact"
                        })

        # Build overall AI Review Summary
        critical_cnt = sum(1 for f in findings if f.get("severity") == "Critical")
        high_cnt = sum(1 for f in findings if f.get("severity") == "High")
        medium_cnt = sum(1 for f in findings if f.get("severity") == "Medium")

        overall_summary = {
            "diff_summary": f"Diff between `{analysis['base_revision']}` and `{analysis['target_revision']}`: {analysis['total_files_changed']} files changed (+{analysis['total_additions']} / -{analysis['total_deletions']}).",
            "findings_count": len(findings),
            "severity_breakdown": {"Critical": critical_cnt, "High": high_cnt, "Medium": medium_cnt},
            "blast_radius_score": kg_impact.get("blast_radius_score", 0),
            "impact_risk": kg_impact.get("impact_risk", "Low"),
            "changed_symbols": changed_symbols
        }

        return {
            "repository_id": str(repo_id),
            "base_revision": analysis["base_revision"],
            "target_revision": analysis["target_revision"],
            "total_files_changed": analysis["total_files_changed"],
            "total_additions": analysis["total_additions"],
            "total_deletions": analysis["total_deletions"],
            "changed_symbols": changed_symbols,
            "impact_analysis": kg_impact,
            "ai_review": {
                "summary": overall_summary,
                "findings": findings
            },
            "files": files,
            "created_at": datetime.utcnow()
        }


git_diff_service = GitDiffService()

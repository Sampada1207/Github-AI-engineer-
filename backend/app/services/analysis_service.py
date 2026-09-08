import re
import os
from typing import List, Dict, Any, Optional

class CodeAnalysisService:
    def analyze_codebase(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes the files of a repository and generates reports for code smells,
        duplicates, security risks, performance issues, and calculates the health score.
        """
        code_smells = []
        security_risks = []
        performance_issues = []
        
        # 1. Static Rule-Based Scans
        for file in files:
            content = file["content"] or ""
            path = file["path"]
            lang = file["language"]
            
            # Analyze line by line
            lines = content.splitlines()
            
            # Metric tracking
            func_lines_count = 0
            in_func = False
            func_name = ""
            func_start = 0
            
            # Scan rules
            for idx, line in enumerate(lines):
                line_num = idx + 1
                stripped = line.strip()
                
                # A. Security scans (hardcoded secrets, dangerous keywords)
                self._check_security_line(stripped, path, line_num, security_risks)
                
                # B. Performance scans (nested loops, recursion, heavy operations)
                self._check_performance_line(stripped, path, line_num, performance_issues)
                
                # C. Code smells scans (complexity, comments, line lengths)
                self._check_smells_line(stripped, path, line_num, code_smells)
                
                # D. Length of functions detector (approximate logic)
                if lang == "Python":
                    if stripped.startswith("def ") or stripped.startswith("async def "):
                        if in_func:
                            self._check_func_length(path, func_name, func_start, line_num - 1, code_smells)
                        in_func = True
                        func_name = stripped.split("(")[0].replace("def ", "").replace("async def ", "").strip()
                        func_start = line_num
                    elif in_func and not line.startswith(("    ", "\t")) and stripped != "":
                        # Function ended (dedentation)
                        self._check_func_length(path, func_name, func_start, line_num - 1, code_smells)
                        in_func = False
                elif lang in ("JavaScript", "TypeScript", "Go"):
                    if stripped.startswith("function ") or "func " in stripped:
                        if in_func:
                            self._check_func_length(path, func_name, func_start, line_num - 1, code_smells)
                        in_func = True
                        func_name = stripped.split("(")[0].replace("function ", "").replace("func ", "").strip()
                        func_start = line_num
            
            # Handle trailing function at EOF
            if in_func:
                self._check_func_length(path, func_name, func_start, len(lines), code_smells)
                
        # 2. Duplicate Code Detection
        duplicate_code = self._detect_duplicates(files)
        
        # 3. Health Score Calculation
        health_score = self._calculate_health_score(code_smells, security_risks, performance_issues, duplicate_code)
        
        return {
            "code_smells": code_smells,
            "duplicate_code": duplicate_code,
            "security_risks": security_risks,
            "performance_issues": performance_issues,
            "health_score": health_score
        }

    def _check_security_line(self, line: str, path: str, line_num: int, risks: List[Dict[str, Any]]):
        # 1. Hardcoded Credentials / Keys
        sec_pattern = re.compile(r'(?:key|secret|password|passwd|token|credential|api_key|private_key|token)\s*[:=]\s*[\'"][a-zA-Z0-9_\-\.\=\+]{8,}[\'"]', re.IGNORECASE)
        # Avoid false positives on imports or variable reassignments
        if sec_pattern.search(line) and not line.startswith(("import", "from")):
            risks.append({
                "file": path,
                "line": line_num,
                "type": "Hardcoded Secret",
                "description": f"Possible hardcoded credential or secret detected: '{line[:40]}...'",
                "severity": "High"
            })
            
        # 2. Dangerous SQL construction
        if ("select" in line.lower() or "insert" in line.lower() or "update" in line.lower()) and ("%" in line or "+ " in line or ".format(" in line or "f\"" in line or "f\'" in line):
            risks.append({
                "file": path,
                "line": line_num,
                "type": "SQL Injection Risk",
                "description": "SQL statement constructed using string formatting/interpolation. Use query parameters instead.",
                "severity": "High"
            })
            
        # 3. Dangerous Commands / Functions
        if "eval(" in line or "exec(" in line or "subprocess.Popen(..., shell=True)" in line:
            risks.append({
                "file": path,
                "line": line_num,
                "type": "Code Execution Vulnerability",
                "description": f"Use of dangerous keyword 'eval/exec' or unsafe shell subprocess: '{line}'",
                "severity": "Critical"
            })

    def _check_performance_line(self, line: str, path: str, line_num: int, bottlenecks: List[Dict[str, Any]]):
        # 1. Heavy loops / Nested calculations
        if "for " in line and "in range(" in line and "len(" in line:
            bottlenecks.append({
                "file": path,
                "line": line_num,
                "type": "Loop Optimization",
                "description": "Avoid calculating collection length inside range loops if collection is static.",
                "severity": "Low"
            })
        # 2. Redundant database sessions
        if ".commit()" in line and "for " in line:
            bottlenecks.append({
                "file": path,
                "line": line_num,
                "type": "Database Performance",
                "description": "Commit statement inside a loop. Consider batch updates to avoid connection overhead.",
                "severity": "Medium"
            })

    def _check_smells_line(self, line: str, path: str, line_num: int, smells: List[Dict[str, Any]]):
        # 1. Overly long lines
        if len(line) > 120:
            smells.append({
                "file": path,
                "line": line_num,
                "type": "Long Line",
                "description": f"Line exceeds 120 characters ({len(line)} chars). Consider breaking it up.",
                "severity": "Low"
            })
        # 2. TODO/FIXME markers
        if "TODO" in line or "FIXME" in line:
            smells.append({
                "file": path,
                "line": line_num,
                "type": "Technical Debt",
                "description": f"Unresolved reminder: '{line}'",
                "severity": "Low"
            })

    def _check_func_length(self, path: str, name: str, start: int, end: int, smells: List[Dict[str, Any]]):
        length = end - start
        if length > 50:
            smells.append({
                "file": path,
                "line": start,
                "type": "Long Function",
                "description": f"Function '{name}' is too long ({length} lines). Consider refactoring it into smaller modules.",
                "severity": "Medium"
            })

    def _detect_duplicates(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rough hash-based algorithm to check for matching code blocks of 6+ lines."""
        duplicates = []
        seen_blocks = {} # block_hash -> (file, line)
        
        for file in files:
            path = file["path"]
            lines = (file["content"] or "").splitlines()
            
            # Check slide of 6 lines
            window_size = 6
            if len(lines) < window_size:
                continue
                
            for idx in range(len(lines) - window_size + 1):
                block = "\n".join([lines[idx + i].strip() for i in range(window_size)])
                # Ignore trivial blank/import blocks
                if len(block.replace("\n", "").strip()) < 30 or "import" in block:
                    continue
                    
                block_hash = hash(block)
                if block_hash in seen_blocks:
                    other_path, other_line = seen_blocks[block_hash]
                    if other_path != path:
                        duplicates.append({
                            "file": path,
                            "line": idx + 1,
                            "duplicate_file": other_path,
                            "duplicate_line": other_line,
                            "description": f"Duplicate block of {window_size} lines found in '{other_path}' at line {other_line}."
                        })
                        # Jump window to avoid overlapping notifications
                        idx += window_size
                else:
                    seen_blocks[block_hash] = (path, idx + 1)
                    
        return duplicates[:15]  # limit to 15 duplicates max to avoid clutter

    def _calculate_health_score(self, smells, risks, performance, duplicates) -> int:
        score = 100
        
        # Deduct per smell
        score -= len(smells) * 1  # -1 pt per smell
        # Deduct per performance issue
        score -= len(performance) * 3  # -3 pt per perf issue
        # Deduct per duplicate
        score -= len(duplicates) * 2  # -2 pt per duplicate
        # Deduct per security risk
        for risk in risks:
            if risk["severity"] == "Critical":
                score -= 15
            elif risk["severity"] == "High":
                score -= 10
            else:
                score -= 5
                
    def generate_repository_summary(
        self,
        files: List[Dict[str, Any]],
        parsed_structures: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Compiles a comprehensive lightweight architectural summary of the repository:
        languages, key entry points, primary modules, key classes/functions, and dependency networks.
        """
        if not files:
            return {
                "summary_text": "Empty repository with no scanned files.",
                "total_files": 0,
                "total_lines": 0,
                "languages": {},
                "key_files": [],
                "modules": [],
                "classes": [],
                "functions": [],
                "dependencies": []
            }

        total_lines = 0
        lang_counts = {}
        key_files = []
        modules = set()
        all_classes = []
        all_functions = []
        all_dependencies = set()
        inheritance_map = {}

        entrypoint_names = {
            "main.py", "app.py", "server.py", "wsgi.py", "manage.py",
            "index.ts", "index.tsx", "index.js", "app.tsx", "page.tsx",
            "server.js", "main.go", "main.rs", "App.java", "Application.java",
            "package.json", "requirements.txt", "Dockerfile", "docker-compose.yml"
        }

        for idx, file in enumerate(files):
            path = file["path"]
            name = file.get("name") or os.path.basename(path)
            lang = file.get("language") or "Unknown"
            content = file.get("content") or ""
            file_lines = len(content.splitlines())
            total_lines += file_lines

            lang_counts[lang] = lang_counts.get(lang, 0) + 1

            # Detect key files
            if name.lower() in entrypoint_names or "/" not in path:
                key_files.append({"path": path, "language": lang, "lines": file_lines})

            # Detect module directories
            dir_name = os.path.dirname(path)
            if dir_name:
                top_dir = dir_name.split("/")[0]
                modules.add(top_dir)

            # Process parsed structure
            if parsed_structures and idx < len(parsed_structures):
                parsed = parsed_structures[idx]
            else:
                from app.services.parser_service import parser_service
                parsed = parser_service.parse_file(content, path, lang)

            for cls in parsed.get("classes", []):
                all_classes.append({
                    "name": cls["name"],
                    "file": path,
                    "bases": cls.get("bases", []),
                    "methods": cls.get("methods", [])
                })
                if cls.get("bases"):
                    inheritance_map[cls["name"]] = cls["bases"]

            for fn in parsed.get("functions", []):
                if not fn.get("parent_symbol"):  # top-level functions
                    all_functions.append({
                        "name": fn["name"],
                        "file": path,
                        "calls": fn.get("calls", [])
                    })

            for dep in parsed.get("dependencies", []):
                all_dependencies.add(dep)

        # Build readable Markdown summary
        key_files_md = "\n".join([f"- `{kf['path']}` ({kf['language']}, {kf['lines']} lines)" for kf in key_files[:10]]) or "- None identified"
        modules_md = ", ".join(sorted(list(modules))) or "root"
        classes_md = "\n".join([
            f"- `{c['name']}` (in `{c['file']}`)" + (f" extends {', '.join(c['bases'])}" if c['bases'] else "")
            for c in all_classes[:15]
        ]) or "- No exported classes"
        functions_md = "\n".join([
            f"- `{f['name']}()` (in `{f['file']}`)"
            for f in all_functions[:15]
        ]) or "- No top-level functions"
        deps_md = ", ".join(sorted(list(all_dependencies))[:20]) or "None"

        summary_text = (
            f"## Repository Architecture Overview\n\n"
            f"- **Total Files**: {len(files)} | **Total Lines of Code**: {total_lines:,}\n"
            f"- **Primary Languages**: {', '.join([f'{l} ({c} files)' for l, c in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)[:5]])}\n"
            f"- **Core Modules/Packages**: {modules_md}\n\n"
            f"### Key Entry Points & Configuration\n{key_files_md}\n\n"
            f"### Primary Classes & Entities\n{classes_md}\n\n"
            f"### Key Functions & Entrypoints\n{functions_md}\n\n"
            f"### Core External Dependencies\n`{deps_md}`\n"
        )

        return {
            "summary_text": summary_text,
            "total_files": len(files),
            "total_lines": total_lines,
            "languages": lang_counts,
            "key_files": key_files[:15],
            "modules": sorted(list(modules)),
            "classes": all_classes[:25],
            "functions": all_functions[:25],
            "dependencies": sorted(list(all_dependencies))[:30]
        }

analysis_service = CodeAnalysisService()

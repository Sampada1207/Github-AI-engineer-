import re
from typing import List, Dict, Any

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
                
        # Keep inside [0, 100]
        return max(0, min(100, score))

analysis_service = CodeAnalysisService()

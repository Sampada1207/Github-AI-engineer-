import re
from typing import List, Dict, Any
from tree_sitter import Language, Parser, Query, QueryCursor

# Import official language bindings
try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    import tree_sitter_java as tsjava
    
    PY_LANG = Language(tspython.language())
    JS_LANG = Language(tsjavascript.language())
    TS_LANG = Language(tstypescript.language_typescript())
    TSX_LANG = Language(tstypescript.language_tsx())
    JAVA_LANG = Language(tsjava.language())
    
    HAS_TREE_SITTER = True
except Exception as e:
    print(f"Tree-sitter language packages loading failed: {e}. Fallback parser activated.")
    HAS_TREE_SITTER = False

class ParserService:
    def __init__(self):
        self.parsers = {}
        self.queries = {}
        
        if HAS_TREE_SITTER:
            try:
                # Initialize parsers
                self.parsers["python"] = Parser(PY_LANG)
                self.parsers["javascript"] = Parser(JS_LANG)
                self.parsers["typescript"] = Parser(TS_LANG)
                self.parsers["tsx"] = Parser(TSX_LANG)
                self.parsers["java"] = Parser(JAVA_LANG)
                
                # Set up queries
                self.queries["python"] = Query(PY_LANG, """
                    (class_definition name: (identifier) @class_name)
                    (function_definition name: (identifier) @func_name)
                    (import_statement) @import
                    (import_from_statement) @import_from
                """)
                
                js_query = """
                    (class_declaration name: (identifier) @class_name)
                    (function_declaration name: (identifier) @func_name)
                    (method_definition name: (property_identifier) @method_name)
                    (import_statement) @import
                """
                ts_query = """
                    (class_declaration name: (type_identifier) @class_name)
                    (function_declaration name: (identifier) @func_name)
                    (method_definition name: (property_identifier) @method_name)
                    (import_statement) @import
                """
                self.queries["javascript"] = Query(JS_LANG, js_query)
                self.queries["typescript"] = Query(TS_LANG, ts_query)
                self.queries["tsx"] = Query(TSX_LANG, ts_query)
                
                self.queries["java"] = Query(JAVA_LANG, """
                    (class_declaration name: (identifier) @class_name)
                    (method_declaration name: (identifier) @method_name)
                    (constructor_declaration name: (identifier) @constructor_name)
                    (import_declaration) @import
                """)
            except Exception as e:
                print(f"Failed to compile tree-sitter queries: {e}")

    def parse_file(self, content: str, path: str, language: str) -> Dict[str, Any]:
        """
        Parses a file to extract classes, functions, imports, and dependencies.
        Uses Tree-sitter for Python, JS, TS, and Java; falls back to regex.
        """
        if not content:
            return {"classes": [], "functions": [], "imports": [], "dependencies": []}

        lang_key = language.lower()
        
        # Mapping to parser keys
        lang_mapping = {
            "python": "python",
            "javascript": "javascript",
            "javascript react": "javascript",
            "typescript": "typescript",
            "typescript react": "tsx",
            "java": "java"
        }
        
        parser_key = lang_mapping.get(lang_key)
        
        if HAS_TREE_SITTER and parser_key in self.parsers and parser_key in self.queries:
            return self._parse_tree_sitter(content, parser_key)
            
        # Regex Fallbacks
        if lang_key == "python":
            return self._parse_python_regex(content)
        elif lang_key in ("javascript", "typescript", "typescript react", "javascript react"):
            return self._parse_js_ts_regex(content)
        elif lang_key == "java":
            return self._parse_java_regex(content)
        else:
            return self._parse_generic(content)

    def _parse_tree_sitter(self, content: str, lang_key: str) -> Dict[str, Any]:
        classes = []
        functions = []
        imports = []
        dependencies = []
        
        try:
            parser = self.parsers[lang_key]
            query = self.queries[lang_key]
            
            tree = parser.parse(bytes(content, "utf8"))
            root = tree.root_node
            
            cursor = QueryCursor(query)
            captures = cursor.captures(root)
            
            # Extract classes
            class_nodes = captures.get("class_name", [])
            for node in class_nodes:
                class_node = node.parent
                if class_node:
                    start_line = class_node.start_point[0] + 1
                    end_line = class_node.end_point[0] + 1
                    classes.append({
                        "name": node.text.decode('utf8', errors='ignore'),
                        "start_line": start_line,
                        "end_line": end_line,
                        "content": class_node.text.decode('utf8', errors='ignore')
                    })
                    
            # Extract functions / methods
            func_nodes = (
                captures.get("func_name", []) + 
                captures.get("method_name", []) + 
                captures.get("constructor_name", [])
            )
            for node in func_nodes:
                func_node = node.parent
                if func_node:
                    start_line = func_node.start_point[0] + 1
                    end_line = func_node.end_point[0] + 1
                    functions.append({
                        "name": node.text.decode('utf8', errors='ignore'),
                        "start_line": start_line,
                        "end_line": end_line,
                        "content": func_node.text.decode('utf8', errors='ignore')
                    })
                    
            # Extract imports and dependencies
            import_nodes = captures.get("import", []) + captures.get("import_from", [])
            for node in import_nodes:
                text = node.text.decode('utf8', errors='ignore')
                imports.append(text)
                
                # Dependency mappings
                if lang_key == "python":
                    parts = text.split()
                    if len(parts) > 1:
                        if parts[0] == "import":
                            for item in parts[1].split(","):
                                dependencies.append(item.strip().split(".")[0])
                        elif parts[0] == "from":
                            dependencies.append(parts[1].split(".")[0])
                elif lang_key in ("javascript", "typescript", "tsx"):
                    match = re.search(r'from\s+[\'"](.+?)[\'"]', text)
                    if match:
                        dep = match.group(1)
                        if not dep.startswith("."):
                            dependencies.append(dep)
                elif lang_key == "java":
                    # import x.y.z;
                    match = re.search(r'import\s+(.+?);', text)
                    if match:
                        pkg = match.group(1).split(".")[0]
                        dependencies.append(pkg)
                        
        except Exception as e:
            print(f"Tree-sitter parse execution error for {lang_key}: {e}")
            # fall back to regex
            if lang_key == "python":
                return self._parse_python_regex(content)
            elif lang_key in ("javascript", "typescript", "tsx"):
                return self._parse_js_ts_regex(content)
            elif lang_key == "java":
                return self._parse_java_regex(content)
                
        return {
            "classes": classes,
            "functions": functions,
            "imports": list(set(imports)),
            "dependencies": list(set(dependencies))
        }

    # ================= REGEX FALLBACK PARSERS =================
    def _parse_python_regex(self, content: str) -> Dict[str, Any]:
        classes = []
        functions = []
        imports = []
        dependencies = []
        
        try:
            tree = ast.parse(content)
            lines = content.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                        dependencies.append(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    imports.append(module)
                    dependencies.append(module.split('.')[0])
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno,
                        "content": "\n".join(lines[node.lineno - 1 : node.end_lineno])
                    })
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    functions.append({
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno,
                        "content": "\n".join(lines[node.lineno - 1 : node.end_lineno])
                    })
        except Exception:
            return self._parse_generic(content)
            
        return {
            "classes": classes,
            "functions": functions,
            "imports": list(set(imports)),
            "dependencies": list(set(dependencies))
        }

    def _parse_js_ts_regex(self, content: str) -> Dict[str, Any]:
        classes = []
        functions = []
        imports = []
        dependencies = []
        
        lines = content.splitlines()
        import_pattern = re.compile(r'(?:import|export)\s+.*?\s+from\s+[\'"](.+?)[\'"]')
        require_pattern = re.compile(r'require\s*\(\s*[\'"](.+?)[\'"]\s*\)')
        class_pattern = re.compile(r'(?:export\s+)?class\s+(\w+)')
        func_pattern = re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\b')
        
        for i, line in enumerate(lines):
            imp_match = import_pattern.search(line) or require_pattern.search(line)
            if imp_match:
                dep = imp_match.group(1)
                imports.append(dep)
                if not dep.startswith('.'):
                    dependencies.append(dep)
            
            class_match = class_pattern.search(line)
            if class_match:
                name = class_match.group(1)
                end = self._find_closing_brace(lines, i + 1)
                classes.append({
                    "name": name,
                    "start_line": i + 1,
                    "end_line": end,
                    "content": "\n".join(lines[i : end])
                })
                
            func_match = func_pattern.search(line)
            if func_match:
                name = func_match.group(1)
                end = self._find_closing_brace(lines, i + 1)
                functions.append({
                    "name": name,
                    "start_line": i + 1,
                    "end_line": end,
                    "content": "\n".join(lines[i : end])
                })
                
        return {
            "classes": classes,
            "functions": functions,
            "imports": list(set(imports)),
            "dependencies": list(set(dependencies))
        }

    def _parse_java_regex(self, content: str) -> Dict[str, Any]:
        classes = []
        functions = []
        imports = []
        dependencies = []
        
        lines = content.splitlines()
        import_pattern = re.compile(r'import\s+(.+?);')
        class_pattern = re.compile(r'(?:public|private|protected)?\s*class\s+(\w+)')
        method_pattern = re.compile(r'(?:public|private|protected|static|\s) +[\w\<\>\[\]]+\s+(\w+) *\([^\)]*\) *(?:throws +[\w\.]+(?:, *[\w\.]+)*)? *\{')
        
        for i, line in enumerate(lines):
            imp_match = import_pattern.search(line)
            if imp_match:
                pkg = imp_match.group(1)
                imports.append(pkg)
                dependencies.append(pkg.split('.')[0])
                
            class_match = class_pattern.search(line)
            if class_match:
                name = class_match.group(1)
                end = self._find_closing_brace(lines, i + 1)
                classes.append({
                    "name": name,
                    "start_line": i + 1,
                    "end_line": end,
                    "content": "\n".join(lines[i : end])
                })
                
            method_match = method_pattern.search(line)
            if method_match:
                name = method_match.group(1)
                if name != "class":  # prevent false matches
                    end = self._find_closing_brace(lines, i + 1)
                    functions.append({
                        "name": name,
                        "start_line": i + 1,
                        "end_line": end,
                        "content": "\n".join(lines[i : end])
                    })
                    
        return {
            "classes": classes,
            "functions": functions,
            "imports": list(set(imports)),
            "dependencies": list(set(dependencies))
        }

    def _parse_generic(self, content: str) -> Dict[str, Any]:
        return {"classes": [], "functions": [], "imports": [], "dependencies": []}

    def _find_closing_brace(self, lines: List[str], start_line: int) -> int:
        brace_count = 0
        opened = False
        for idx in range(start_line - 1, len(lines)):
            line = lines[idx]
            for char in line:
                if char == '{':
                    brace_count += 1
                    opened = True
                elif char == '}':
                    brace_count -= 1
            if opened and brace_count <= 0:
                return idx + 1
        return len(lines)

    def create_semantic_chunks(self, file_content: str, file_path: str, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Semantic chunk compiler breaking code down by structures."""
        chunks = []
        lines = file_content.splitlines()
        total_lines = len(lines)
        chunked_lines = set()
        
        # 1. Classes
        for cls in parsed_data.get("classes", []):
            start, end = cls["start_line"], cls["end_line"]
            chunks.append({
                "chunk_id": f"{file_path}_class_{cls['name']}_{start}_{end}",
                "content": cls["content"],
                "start_line": start,
                "end_line": end,
                "chunk_type": "class"
            })
            for l in range(start, end + 1):
                chunked_lines.add(l)
                
        # 2. Functions
        for func in parsed_data.get("functions", []):
            start, end = func["start_line"], func["end_line"]
            is_inside_class = any(start >= c["start_line"] and end <= c["end_line"] for c in parsed_data.get("classes", []))
            if not is_inside_class:
                chunks.append({
                    "chunk_id": f"{file_path}_func_{func['name']}_{start}_{end}",
                    "content": func["content"],
                    "start_line": start,
                    "end_line": end,
                    "chunk_type": "function"
                })
                for l in range(start, end + 1):
                    chunked_lines.add(l)
                    
        # 3. Module bodies
        module_lines = []
        start_line = None
        for idx in range(total_lines):
            line_num = idx + 1
            if line_num not in chunked_lines:
                if start_line is None:
                    start_line = line_num
                module_lines.append(lines[idx])
            else:
                if module_lines:
                    content = "\n".join(module_lines)
                    if content.strip():
                        chunks.append({
                            "chunk_id": f"{file_path}_module_{start_line}_{line_num - 1}",
                            "content": content,
                            "start_line": start_line,
                            "end_line": line_num - 1,
                            "chunk_type": "module"
                        })
                    module_lines = []
                    start_line = None
                    
        if module_lines:
            content = "\n".join(module_lines)
            if content.strip():
                chunks.append({
                    "chunk_id": f"{file_path}_module_{start_line}_{total_lines}",
                    "content": content,
                    "start_line": start_line,
                    "end_line": total_lines,
                    "chunk_type": "module"
                })
                
        # Fallback to line chunks if none created
        if not chunks:
            chunk_size = 80
            overlap = 20
            i = 0
            while i < total_lines:
                end = min(i + chunk_size, total_lines)
                chunks.append({
                    "chunk_id": f"{file_path}_chunk_{i + 1}_{end}",
                    "content": "\n".join(lines[i:end]),
                    "start_line": i + 1,
                    "end_line": end,
                    "chunk_type": "module"
                })
                i += (chunk_size - overlap)
                
        return chunks

parser_service = ParserService()

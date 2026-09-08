import re
import ast
import os
from typing import List, Dict, Any, Optional

try:
    from tree_sitter import Language, Parser, Query, QueryCursor
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
    print(f"Tree-sitter language packages loading failed: {e}. Fallback AST/regex parser activated.")
    HAS_TREE_SITTER = False


class ParserService:
    def __init__(self):
        self.parsers = {}
        self.queries = {}

        if HAS_TREE_SITTER:
            try:
                self.parsers["python"] = Parser(PY_LANG)
                self.parsers["javascript"] = Parser(JS_LANG)
                self.parsers["typescript"] = Parser(TS_LANG)
                self.parsers["tsx"] = Parser(TSX_LANG)
                self.parsers["java"] = Parser(JAVA_LANG)

                self.queries["python"] = Query(PY_LANG, """
                    (class_definition 
                        name: (identifier) @class_name
                        superclasses: (argument_list)? @class_bases)
                    (function_definition 
                        name: (identifier) @func_name
                        parameters: (parameters) @func_params)
                    (call function: (identifier) @call_name)
                    (call function: (attribute attribute: (identifier) @call_method))
                    (import_statement) @import
                    (import_from_statement) @import_from
                """)

                js_ts_query = """
                    (class_declaration 
                        name: (identifier) @class_name
                        heritage: (class_heritage)? @class_heritage)
                    (function_declaration 
                        name: (identifier) @func_name
                        parameters: (formal_parameters) @func_params)
                    (method_definition 
                        name: (property_identifier) @method_name
                        parameters: (formal_parameters) @method_params)
                    (call_expression function: (identifier) @call_name)
                    (call_expression function: (member_expression property: (property_identifier) @call_method))
                    (import_statement) @import
                    (export_statement) @export
                """
                ts_query = """
                    (class_declaration 
                        name: (type_identifier) @class_name
                        heritage: (class_heritage)? @class_heritage)
                    (function_declaration 
                        name: (identifier) @func_name
                        parameters: (formal_parameters) @func_params)
                    (method_definition 
                        name: (property_identifier) @method_name
                        parameters: (formal_parameters) @method_params)
                    (call_expression function: (identifier) @call_name)
                    (call_expression function: (member_expression property: (property_identifier) @call_method))
                    (import_statement) @import
                    (export_statement) @export
                """

                self.queries["javascript"] = Query(JS_LANG, js_ts_query)
                self.queries["typescript"] = Query(TS_LANG, ts_query)
                self.queries["tsx"] = Query(TSX_LANG, ts_query)

                self.queries["java"] = Query(JAVA_LANG, """
                    (class_declaration 
                        name: (identifier) @class_name
                        superclass: (superclass)? @superclass
                        interfaces: (super_interfaces)? @interfaces)
                    (method_declaration 
                        name: (identifier) @method_name
                        parameters: (formal_parameters) @method_params)
                    (constructor_declaration 
                        name: (identifier) @constructor_name
                        parameters: (formal_parameters) @constructor_params)
                    (method_invocation name: (identifier) @call_name)
                    (import_declaration) @import
                """)
            except Exception as e:
                print(f"Failed to compile tree-sitter queries: {e}")

    def parse_file(self, content: str, path: str, language: str) -> Dict[str, Any]:
        """
        Parses source code to extract structural elements:
        classes, functions, methods, variables/constants, imports, and relationships.
        """
        if not content or not content.strip():
            return {
                "classes": [],
                "functions": [],
                "variables": [],
                "imports": [],
                "dependencies": [],
                "relationships": {
                    "inheritance": [],
                    "containment": [],
                    "calls": [],
                    "imports": []
                }
            }

        lang_key = (language or "unknown").lower()
        lang_mapping = {
            "python": "python",
            "javascript": "javascript",
            "javascript react": "javascript",
            "typescript": "typescript",
            "typescript react": "tsx",
            "java": "java"
        }
        parser_key = lang_mapping.get(lang_key)

        # Primary: Python AST parser is exceptionally accurate for Python semantics
        if lang_key == "python":
            res = self._parse_python_ast(content, path)
            if res and (res["classes"] or res["functions"] or res["imports"]):
                return res

        # Tree-sitter for JS/TS/TSX/Java and Python fallback
        if HAS_TREE_SITTER and parser_key in self.parsers and parser_key in self.queries:
            try:
                res = self._parse_tree_sitter(content, parser_key, path)
                if res and (res["classes"] or res["functions"] or res["imports"]):
                    return res
            except Exception as e:
                print(f"Tree-sitter parse execution error for {lang_key}: {e}")

        # Regex Fallbacks
        if lang_key in ("javascript", "typescript", "typescript react", "javascript react", "tsx", "jsx"):
            return self._parse_js_ts_regex(content, path)
        elif lang_key == "java":
            return self._parse_java_regex(content, path)
        elif lang_key == "python":
            return self._parse_python_regex(content, path)
        else:
            return self._parse_generic(content, path)

    # ================= PYTHON AST PARSER =================
    def _parse_python_ast(self, content: str, path: str) -> Dict[str, Any]:
        classes = []
        functions = []
        variables = []
        imports = []
        dependencies = set()
        inheritance = []
        containment = []
        calls_rel = []

        try:
            tree = ast.parse(content)
            lines = content.splitlines()

            for node in ast.iter_child_nodes(tree):
                # 1. Imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imp_text = f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
                        imports.append(imp_text)
                        root_pkg = alias.name.split(".")[0]
                        dependencies.add(root_pkg)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    names = [a.name for a in node.names]
                    imp_text = f"from {mod} import {', '.join(names)}"
                    imports.append(imp_text)
                    if mod:
                        root_pkg = mod.split(".")[0]
                        dependencies.add(root_pkg)

                # 2. Top-level Variables / Constants
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_name = target.id
                            start_l = node.lineno
                            end_l = getattr(node, "end_lineno", start_l)
                            var_type = "constant" if var_name.isupper() else "variable"
                            var_content = "\n".join(lines[start_l - 1:end_l])
                            variables.append({
                                "name": var_name,
                                "type": var_type,
                                "start_line": start_l,
                                "end_line": end_l,
                                "parent_symbol": None,
                                "content": var_content
                            })

                # 3. Classes
                elif isinstance(node, ast.ClassDef):
                    bases = []
                    for b in node.bases:
                        if isinstance(b, ast.Name):
                            bases.append(b.id)
                        elif isinstance(b, ast.Attribute):
                            bases.append(f"{ast.unparse(b)}")
                        else:
                            try:
                                bases.append(ast.unparse(b))
                            except Exception:
                                pass

                    class_start = node.lineno
                    class_end = getattr(node, "end_lineno", class_start)
                    class_content = "\n".join(lines[class_start - 1:class_end])
                    docstring = ast.get_docstring(node) or ""

                    if bases:
                        inheritance.append({"class": node.name, "bases": bases})

                    method_names = []
                    # Inspect class body for methods
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_names.append(item.name)
                            m_start = item.lineno
                            m_end = getattr(item, "end_lineno", m_start)
                            m_content = "\n".join(lines[m_start - 1:m_end])
                            m_params = [arg.arg for arg in item.args.args]
                            m_calls = self._extract_ast_calls(item)
                            m_doc = ast.get_docstring(item) or ""

                            functions.append({
                                "name": item.name,
                                "start_line": m_start,
                                "end_line": m_end,
                                "parent_symbol": node.name,
                                "symbol_type": "method",
                                "params": m_params,
                                "calls": m_calls,
                                "bases": [],
                                "docstring": m_doc,
                                "content": m_content
                            })
                            containment.append({
                                "parent": node.name,
                                "child": item.name,
                                "child_type": "method"
                            })
                            for callee in m_calls:
                                calls_rel.append({"caller": f"{node.name}.{item.name}", "callee": callee})

                    classes.append({
                        "name": node.name,
                        "start_line": class_start,
                        "end_line": class_end,
                        "parent_symbol": None,
                        "symbol_type": "class",
                        "bases": bases,
                        "methods": method_names,
                        "docstring": docstring,
                        "content": class_content
                    })

                # 4. Top-level Functions
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    f_start = node.lineno
                    f_end = getattr(node, "end_lineno", f_start)
                    f_content = "\n".join(lines[f_start - 1:f_end])
                    f_params = [arg.arg for arg in node.args.args]
                    f_calls = self._extract_ast_calls(node)
                    f_doc = ast.get_docstring(node) or ""

                    functions.append({
                        "name": node.name,
                        "start_line": f_start,
                        "end_line": f_end,
                        "parent_symbol": None,
                        "symbol_type": "function",
                        "params": f_params,
                        "calls": f_calls,
                        "bases": [],
                        "docstring": f_doc,
                        "content": f_content
                    })
                    for callee in f_calls:
                        calls_rel.append({"caller": node.name, "callee": callee})

            return {
                "classes": classes,
                "functions": functions,
                "variables": variables,
                "imports": list(dict.fromkeys(imports)),
                "dependencies": sorted(list(dependencies)),
                "relationships": {
                    "inheritance": inheritance,
                    "containment": containment,
                    "calls": calls_rel[:50],
                    "imports": [{"statement": imp} for imp in imports]
                }
            }
        except Exception as e:
            return self._parse_python_regex(content, path)

    def _extract_ast_calls(self, node: ast.AST) -> List[str]:
        """Helper to extract function and method call names inside an AST node."""
        calls = []
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Name):
                    calls.append(n.func.id)
                elif isinstance(n.func, ast.Attribute):
                    calls.append(n.func.attr)
        return list(dict.fromkeys(calls))[:20]

    # ================= TREE SITTER PARSER =================
    def _parse_tree_sitter(self, content: str, lang_key: str, path: str) -> Dict[str, Any]:
        classes = []
        functions = []
        variables = []
        imports = []
        dependencies = set()
        inheritance = []
        containment = []
        calls_rel = []

        parser = self.parsers[lang_key]
        query = self.queries[lang_key]
        lines = content.splitlines()

        tree = parser.parse(bytes(content, "utf8"))
        root = tree.root_node
        cursor = QueryCursor(query)
        captures = cursor.captures(root)

        # Classes
        class_nodes = captures.get("class_name", [])
        for node in class_nodes:
            class_node = node.parent
            if class_node:
                start_l = class_node.start_point[0] + 1
                end_l = class_node.end_point[0] + 1
                c_name = node.text.decode('utf8', errors='ignore')
                c_content = "\n".join(lines[start_l - 1:end_l]) if lines else ""

                bases = []
                # Check for heritage / extends
                for child in class_node.children:
                    if child.type in ("class_heritage", "superclass", "super_interfaces", "argument_list"):
                        base_text = child.text.decode('utf8', errors='ignore').strip("():{}")
                        for part in re.split(r'[, ]+', base_text):
                            if part and part not in ("extends", "implements", "class"):
                                bases.append(part.strip())

                if bases:
                    inheritance.append({"class": c_name, "bases": bases})

                classes.append({
                    "name": c_name,
                    "start_line": start_l,
                    "end_line": end_l,
                    "parent_symbol": None,
                    "symbol_type": "class",
                    "bases": bases,
                    "methods": [],
                    "content": c_content
                })

        # Functions / Methods
        func_nodes = captures.get("func_name", [])
        method_nodes = captures.get("method_name", []) + captures.get("constructor_name", [])

        # Process methods with parent containment
        for node in method_nodes:
            func_node = node.parent
            if func_node:
                start_l = func_node.start_point[0] + 1
                end_l = func_node.end_point[0] + 1
                m_name = node.text.decode('utf8', errors='ignore')
                m_content = "\n".join(lines[start_l - 1:end_l]) if lines else ""

                # Find parent class
                parent_cls = None
                for cls in classes:
                    if cls["start_line"] <= start_l and cls["end_line"] >= end_l:
                        parent_cls = cls["name"]
                        cls["methods"].append(m_name)
                        break

                functions.append({
                    "name": m_name,
                    "start_line": start_l,
                    "end_line": end_l,
                    "parent_symbol": parent_cls,
                    "symbol_type": "method",
                    "params": [],
                    "calls": [],
                    "bases": [],
                    "content": m_content
                })
                if parent_cls:
                    containment.append({"parent": parent_cls, "child": m_name, "child_type": "method"})

        for node in func_nodes:
            func_node = node.parent
            if func_node:
                start_l = func_node.start_point[0] + 1
                end_l = func_node.end_point[0] + 1
                f_name = node.text.decode('utf8', errors='ignore')
                f_content = "\n".join(lines[start_l - 1:end_l]) if lines else ""

                functions.append({
                    "name": f_name,
                    "start_line": start_l,
                    "end_line": end_l,
                    "parent_symbol": None,
                    "symbol_type": "function",
                    "params": [],
                    "calls": [],
                    "bases": [],
                    "content": f_content
                })

        # Imports & Dependencies
        import_nodes = captures.get("import", []) + captures.get("import_from", [])
        for node in import_nodes:
            text = node.text.decode('utf8', errors='ignore').strip()
            imports.append(text)
            if lang_key == "python":
                parts = text.split()
                if len(parts) > 1:
                    if parts[0] == "import":
                        for item in parts[1].split(","):
                            dependencies.add(item.strip().split(".")[0])
                    elif parts[0] == "from":
                        dependencies.add(parts[1].split(".")[0])
            elif lang_key in ("javascript", "typescript", "tsx"):
                match = re.search(r'from\s+[\'"](.+?)[\'"]', text) or re.search(r'require\s*\(\s*[\'"](.+?)[\'"]\s*\)', text)
                if match:
                    dep = match.group(1)
                    if not dep.startswith("."):
                        dependencies.add(dep.split("/")[0])
            elif lang_key == "java":
                match = re.search(r'import\s+(?:static\s+)?(.+?);', text)
                if match:
                    dependencies.add(match.group(1).split(".")[0])

        return {
            "classes": classes,
            "functions": functions,
            "variables": variables,
            "imports": list(dict.fromkeys(imports)),
            "dependencies": sorted(list(dependencies)),
            "relationships": {
                "inheritance": inheritance,
                "containment": containment,
                "calls": calls_rel,
                "imports": [{"statement": imp} for imp in imports]
            }
        }

    # ================= REGEX FALLBACK PARSERS =================
    def _parse_python_regex(self, content: str, path: str) -> Dict[str, Any]:
        classes = []
        functions = []
        variables = []
        imports = []
        dependencies = set()
        inheritance = []

        lines = content.splitlines()
        class_pattern = re.compile(r'^\s*class\s+(\w+)(?:\((.*?)\))?:')
        func_pattern = re.compile(r'^\s*(?:async\s+)?def\s+(\w+)\s*\((.*?)\):')
        import_pattern = re.compile(r'^\s*(?:import\s+(.+)|from\s+([\w\.]+)\s+import\s+(.+))')

        current_class = None
        for i, line in enumerate(lines):
            # Imports
            imp_m = import_pattern.match(line)
            if imp_m:
                imports.append(line.strip())
                if imp_m.group(1):
                    for part in imp_m.group(1).split(","):
                        dependencies.add(part.strip().split(".")[0])
                elif imp_m.group(2):
                    dependencies.add(imp_m.group(2).split(".")[0])

            # Classes
            cls_m = class_pattern.match(line)
            if cls_m:
                name = cls_m.group(1)
                bases_str = cls_m.group(2) or ""
                bases = [b.strip() for b in bases_str.split(",") if b.strip()]
                end_l = self._find_python_block_end(lines, i)
                classes.append({
                    "name": name,
                    "start_line": i + 1,
                    "end_line": end_l,
                    "parent_symbol": None,
                    "symbol_type": "class",
                    "bases": bases,
                    "methods": [],
                    "content": "\n".join(lines[i:end_l])
                })
                if bases:
                    inheritance.append({"class": name, "bases": bases})
                current_class = name

            # Functions
            fn_m = func_pattern.match(line)
            if fn_m:
                name = fn_m.group(1)
                params_str = fn_m.group(2) or ""
                params = [p.strip().split(":")[0].strip() for p in params_str.split(",") if p.strip()]
                end_l = self._find_python_block_end(lines, i)
                is_method = line.startswith(("    ", "\t")) and current_class is not None
                functions.append({
                    "name": name,
                    "start_line": i + 1,
                    "end_line": end_l,
                    "parent_symbol": current_class if is_method else None,
                    "symbol_type": "method" if is_method else "function",
                    "params": params,
                    "calls": [],
                    "bases": [],
                    "content": "\n".join(lines[i:end_l])
                })

        return {
            "classes": classes,
            "functions": functions,
            "variables": variables,
            "imports": list(dict.fromkeys(imports)),
            "dependencies": sorted(list(dependencies)),
            "relationships": {
                "inheritance": inheritance,
                "containment": [],
                "calls": [],
                "imports": [{"statement": imp} for imp in imports]
            }
        }

    def _find_python_block_end(self, lines: List[str], start_idx: int) -> int:
        initial_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
        for idx in range(start_idx + 1, len(lines)):
            line = lines[idx]
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= initial_indent:
                return idx
        return len(lines)

    def _parse_js_ts_regex(self, content: str, path: str) -> Dict[str, Any]:
        classes = []
        functions = []
        variables = []
        imports = []
        dependencies = set()
        inheritance = []

        lines = content.splitlines()
        import_pattern = re.compile(r'(?:import|export)\s+.*?\s+from\s+[\'"](.+?)[\'"]')
        require_pattern = re.compile(r'require\s*\(\s*[\'"](.+?)[\'"]\s*\)')
        class_pattern = re.compile(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?')
        func_pattern = re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\((.*?)\)')
        arrow_pattern = re.compile(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>')

        for i, line in enumerate(lines):
            imp_m = import_pattern.search(line) or require_pattern.search(line)
            if imp_m:
                dep = imp_m.group(1)
                imports.append(line.strip())
                if not dep.startswith('.'):
                    dependencies.add(dep.split("/")[0])

            cls_m = class_pattern.search(line)
            if cls_m:
                name = cls_m.group(1)
                base = cls_m.group(2)
                bases = [base] if base else []
                end_l = self._find_closing_brace(lines, i + 1)
                classes.append({
                    "name": name,
                    "start_line": i + 1,
                    "end_line": end_l,
                    "parent_symbol": None,
                    "symbol_type": "class",
                    "bases": bases,
                    "methods": [],
                    "content": "\n".join(lines[i:end_l])
                })
                if bases:
                    inheritance.append({"class": name, "bases": bases})

            fn_m = func_pattern.search(line) or arrow_pattern.search(line)
            if fn_m:
                name = fn_m.group(1)
                params_str = fn_m.group(2) if len(fn_m.groups()) >= 2 and fn_m.group(2) else ""
                params = [p.strip().split(":")[0].strip() for p in params_str.split(",") if p.strip()]
                end_l = self._find_closing_brace(lines, i + 1)
                functions.append({
                    "name": name,
                    "start_line": i + 1,
                    "end_line": end_l,
                    "parent_symbol": None,
                    "symbol_type": "function",
                    "params": params,
                    "calls": [],
                    "bases": [],
                    "content": "\n".join(lines[i:end_l])
                })

        return {
            "classes": classes,
            "functions": functions,
            "variables": variables,
            "imports": list(dict.fromkeys(imports)),
            "dependencies": sorted(list(dependencies)),
            "relationships": {
                "inheritance": inheritance,
                "containment": [],
                "calls": [],
                "imports": [{"statement": imp} for imp in imports]
            }
        }

    def _parse_java_regex(self, content: str, path: str) -> Dict[str, Any]:
        classes = []
        functions = []
        imports = []
        dependencies = set()
        inheritance = []

        lines = content.splitlines()
        import_pattern = re.compile(r'import\s+(?:static\s+)?(.+?);')
        class_pattern = re.compile(r'(?:public|private|protected)?\s*class\s+(\w+)(?:\s+extends\s+(\w+))?')
        method_pattern = re.compile(r'(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\((.*?)\)\s*(?:throws\s+[\w\.,\s]+)?\s*\{')

        for i, line in enumerate(lines):
            imp_m = import_pattern.search(line)
            if imp_m:
                pkg = imp_m.group(1)
                imports.append(line.strip())
                dependencies.add(pkg.split('.')[0])

            cls_m = class_pattern.search(line)
            if cls_m:
                name = cls_m.group(1)
                base = cls_m.group(2)
                bases = [base] if base else []
                end_l = self._find_closing_brace(lines, i + 1)
                classes.append({
                    "name": name,
                    "start_line": i + 1,
                    "end_line": end_l,
                    "parent_symbol": None,
                    "symbol_type": "class",
                    "bases": bases,
                    "methods": [],
                    "content": "\n".join(lines[i:end_l])
                })
                if bases:
                    inheritance.append({"class": name, "bases": bases})

            meth_m = method_pattern.search(line)
            if meth_m:
                name = meth_m.group(1)
                if name != "class":
                    end_l = self._find_closing_brace(lines, i + 1)
                    functions.append({
                        "name": name,
                        "start_line": i + 1,
                        "end_line": end_l,
                        "parent_symbol": None,
                        "symbol_type": "method",
                        "params": [],
                        "calls": [],
                        "bases": [],
                        "content": "\n".join(lines[i:end_l])
                    })

        return {
            "classes": classes,
            "functions": functions,
            "variables": [],
            "imports": list(dict.fromkeys(imports)),
            "dependencies": sorted(list(dependencies)),
            "relationships": {
                "inheritance": inheritance,
                "containment": [],
                "calls": [],
                "imports": [{"statement": imp} for imp in imports]
            }
        }

    def _parse_generic(self, content: str, path: str) -> Dict[str, Any]:
        return {
            "classes": [],
            "functions": [],
            "variables": [],
            "imports": [],
            "dependencies": [],
            "relationships": {"inheritance": [], "containment": [], "calls": [], "imports": []}
        }

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

    # ================= SMART SEMANTIC CHUNKING =================
    def create_semantic_chunks(
        self,
        file_content: str,
        file_path: str,
        parsed_data: Dict[str, Any],
        language: str = "Unknown"
    ) -> List[Dict[str, Any]]:
        """
        Compiles smart semantic chunks anchored to classes, methods, functions, and modules.
        Attaches rich structural metadata: symbol_name, symbol_type, parent_symbol, relationships.
        """
        chunks = []
        lines = file_content.splitlines()
        total_lines = len(lines)
        chunked_lines = set()

        # 1. Functions & Methods
        for func in parsed_data.get("functions", []):
            start, end = func["start_line"], func["end_line"]
            name = func.get("name", "anonymous")
            sym_type = func.get("symbol_type", "function")
            parent = func.get("parent_symbol")
            calls = func.get("calls", [])

            chunk_id = f"{file_path}_{sym_type}_{name}_{start}_{end}"
            chunks.append({
                "chunk_id": chunk_id,
                "file_path": file_path,
                "language": language,
                "symbol_name": name,
                "symbol_type": sym_type,
                "parent_symbol": parent,
                "content": func["content"],
                "start_line": start,
                "end_line": end,
                "relationships": {
                    "calls": calls,
                    "parent": parent
                }
            })
            for l in range(start, end + 1):
                chunked_lines.add(l)

        # 2. Classes (Class declarations / headers / smaller classes)
        for cls in parsed_data.get("classes", []):
            start, end = cls["start_line"], cls["end_line"]
            name = cls.get("name", "AnonymousClass")
            bases = cls.get("bases", [])

            # If class is relatively compact (<= 80 lines), can chunk entire class
            # Otherwise chunk class header/definitions if methods are already chunked
            class_lines_uncovered = [l for l in range(start, end + 1) if l not in chunked_lines]
            if class_lines_uncovered or (end - start <= 80):
                content = cls["content"]
                # Cap content if massive
                if len(content) > 3500:
                    content = content[:3500] + "\n... [truncated for embedding limits]"

                chunk_id = f"{file_path}_class_{name}_{start}_{end}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "file_path": file_path,
                    "language": language,
                    "symbol_name": name,
                    "symbol_type": "class",
                    "parent_symbol": None,
                    "content": content,
                    "start_line": start,
                    "end_line": end,
                    "relationships": {
                        "bases": bases,
                        "methods": cls.get("methods", [])
                    }
                })
                for l in range(start, end + 1):
                    chunked_lines.add(l)

        # 3. Top-level Variables / Constants
        for var in parsed_data.get("variables", []):
            start, end = var["start_line"], var["end_line"]
            if start not in chunked_lines:
                chunks.append({
                    "chunk_id": f"{file_path}_{var['type']}_{var['name']}_{start}_{end}",
                    "file_path": file_path,
                    "language": language,
                    "symbol_name": var["name"],
                    "symbol_type": var["type"],
                    "parent_symbol": None,
                    "content": var["content"],
                    "start_line": start,
                    "end_line": end,
                    "relationships": {}
                })
                for l in range(start, end + 1):
                    chunked_lines.add(l)

        # 4. Module-level blocks (imports, config, top-level scripts)
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
                            "file_path": file_path,
                            "language": language,
                            "symbol_name": os.path.basename(file_path),
                            "symbol_type": "module",
                            "parent_symbol": None,
                            "content": content,
                            "start_line": start_line,
                            "end_line": line_num - 1,
                            "relationships": {
                                "imports": parsed_data.get("imports", [])[:10]
                            }
                        })
                    module_lines = []
                    start_line = None

        if module_lines:
            content = "\n".join(module_lines)
            if content.strip():
                chunks.append({
                    "chunk_id": f"{file_path}_module_{start_line}_{total_lines}",
                    "file_path": file_path,
                    "language": language,
                    "symbol_name": os.path.basename(file_path),
                    "symbol_type": "module",
                    "parent_symbol": None,
                    "content": content,
                    "start_line": start_line,
                    "end_line": total_lines,
                    "relationships": {
                        "imports": parsed_data.get("imports", [])[:10]
                    }
                })

        # Fallback to sliding window line chunks if empty
        if not chunks and total_lines > 0:
            chunk_size = 80
            overlap = 20
            i = 0
            while i < total_lines:
                end = min(i + chunk_size, total_lines)
                chunks.append({
                    "chunk_id": f"{file_path}_chunk_{i + 1}_{end}",
                    "file_path": file_path,
                    "language": language,
                    "symbol_name": os.path.basename(file_path),
                    "symbol_type": "module",
                    "parent_symbol": None,
                    "content": "\n".join(lines[i:end]),
                    "start_line": i + 1,
                    "end_line": end,
                    "relationships": {}
                })
                i += (chunk_size - overlap)

        return chunks


parser_service = ParserService()

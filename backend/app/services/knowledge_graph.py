import json
import os
import re
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field, asdict


@dataclass
class GraphNode:
    id: str
    type: str  # repository, file, module, class, function, method, variable
    name: str
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    type: str  # CONTAINS, IMPORTS, CALLS, EXTENDS, DEPENDS_ON
    metadata: Dict[str, Any] = field(default_factory=dict)


class CodeKnowledgeGraph:
    """
    Lightweight, in-memory directed graph representing repository structure, symbols, and relationships.
    Provides fast indexed lookups by symbol name, file path, and relation type.
    """
    def __init__(self, repository_id: str):
        self.repository_id = str(repository_id)
        self.nodes: Dict[str, GraphNode] = {}
        self.out_edges: Dict[str, List[GraphEdge]] = {}
        self.in_edges: Dict[str, List[GraphEdge]] = {}
        
        # Fast lookup indexes
        self.symbol_to_nodes: Dict[str, Set[str]] = {}  # symbol_name.lower() -> node_ids
        self.file_to_nodes: Dict[str, Set[str]] = {}    # file_path -> node_ids

    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node
        if node.id not in self.out_edges:
            self.out_edges[node.id] = []
        if node.id not in self.in_edges:
            self.in_edges[node.id] = []

        # Index by symbol name
        s_key = node.name.lower()
        if s_key not in self.symbol_to_nodes:
            self.symbol_to_nodes[s_key] = set()
        self.symbol_to_nodes[s_key].add(node.id)

        # Index by file path
        if node.file_path:
            if node.file_path not in self.file_to_nodes:
                self.file_to_nodes[node.file_path] = set()
            self.file_to_nodes[node.file_path].add(node.id)

    def add_edge(self, edge: GraphEdge):
        if edge.source_id not in self.out_edges:
            self.out_edges[edge.source_id] = []
        if edge.target_id not in self.in_edges:
            self.in_edges[edge.target_id] = []

        # Prevent duplicate edge of same type and target
        if not any(e.target_id == edge.target_id and e.type == edge.type for e in self.out_edges[edge.source_id]):
            self.out_edges[edge.source_id].append(edge)
            self.in_edges[edge.target_id].append(edge)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository_id": self.repository_id,
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for edges in self.out_edges.values() for e in edges]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeKnowledgeGraph":
        graph = cls(data.get("repository_id", ""))
        for n_data in data.get("nodes", []):
            node = GraphNode(**n_data)
            graph.add_node(node)
        for e_data in data.get("edges", []):
            edge = GraphEdge(**e_data)
            graph.add_edge(edge)
        return graph


class KnowledgeGraphService:
    """
    Manages building, persisting, and querying repository knowledge graphs with strict repo isolation.
    """
    def __init__(self):
        self._cache: Dict[str, CodeKnowledgeGraph] = {}

    def get_graph(self, repository_id: str) -> CodeKnowledgeGraph:
        """Retrieves graph from in-memory cache or loads from database."""
        repo_id = str(repository_id)
        if repo_id in self._cache:
            return self._cache[repo_id]

        # Attempt to load from database
        try:
            from app.database import SessionLocal
            from app.models.models import GeneratedDocumentation
            db = SessionLocal()
            try:
                doc = db.query(GeneratedDocumentation).filter(
                    GeneratedDocumentation.repository_id == repo_id,
                    GeneratedDocumentation.doc_type == "knowledge_graph"
                ).first()
                if doc and doc.content:
                    data = json.loads(doc.content)
                    graph = CodeKnowledgeGraph.from_dict(data)
                    self._cache[repo_id] = graph
                    return graph
            finally:
                db.close()
        except Exception as e:
            print(f"Could not load graph from DB for repo {repo_id}: {e}")

        # Return empty graph
        graph = CodeKnowledgeGraph(repo_id)
        self._cache[repo_id] = graph
        return graph

    def build_graph_from_repository(
        self,
        repository_id: str,
        files_data: List[Dict[str, Any]],
        parsed_structures: Optional[List[Dict[str, Any]]] = None
    ) -> CodeKnowledgeGraph:
        """
        Constructs a complete code knowledge graph from scanned files and parsed AST/Tree-sitter structures.
        """
        repo_id = str(repository_id)
        graph = CodeKnowledgeGraph(repo_id)

        # 1. Root repository node
        repo_node_id = f"repo:{repo_id}"
        graph.add_node(GraphNode(
            id=repo_node_id,
            type="repository",
            name=f"Repository_{repo_id[:8]}",
            metadata={"total_files": len(files_data)}
        ))

        # Index file mapping and parsed structures
        file_node_ids = {}
        for idx, file in enumerate(files_data):
            path = file["path"]
            file_node_id = f"file:{path}"
            file_node_ids[path] = file_node_id

            graph.add_node(GraphNode(
                id=file_node_id,
                type="file",
                name=file.get("name") or os.path.basename(path),
                file_path=path,
                metadata={"language": file.get("language"), "size": file.get("size", 0)}
            ))
            # Repo CONTAINS file
            graph.add_edge(GraphEdge(
                source_id=repo_node_id,
                target_id=file_node_id,
                type="CONTAINS"
            ))

        # Symbol mapping: symbol_name -> node_id
        symbol_node_ids: Dict[str, str] = {}
        all_parsed_list = []

        # 2. Extract and link classes, methods, functions, and variables
        for idx, file in enumerate(files_data):
            path = file["path"]
            file_node_id = file_node_ids[path]
            lang = file.get("language") or "Unknown"

            if parsed_structures and idx < len(parsed_structures):
                parsed = parsed_structures[idx]
            else:
                from app.services.parser_service import parser_service
                parsed = parser_service.parse_file(file.get("content", ""), path, lang)
            all_parsed_list.append(parsed)

            # A. Classes
            for cls in parsed.get("classes", []):
                cls_name = cls["name"]
                cls_node_id = f"class:{path}:{cls_name}"
                symbol_node_ids[cls_name] = cls_node_id

                graph.add_node(GraphNode(
                    id=cls_node_id,
                    type="class",
                    name=cls_name,
                    file_path=path,
                    start_line=cls.get("start_line"),
                    end_line=cls.get("end_line"),
                    metadata={"bases": cls.get("bases", []), "docstring": cls.get("docstring", "")}
                ))
                # File CONTAINS class
                graph.add_edge(GraphEdge(
                    source_id=file_node_id,
                    target_id=cls_node_id,
                    type="CONTAINS"
                ))

            # B. Functions & Methods
            for fn in parsed.get("functions", []):
                fn_name = fn["name"]
                parent_cls = fn.get("parent_symbol")
                sym_type = fn.get("symbol_type", "function")
                fn_node_id = f"{sym_type}:{path}:{parent_cls or 'top'}:{fn_name}"
                if fn_name not in symbol_node_ids:
                    symbol_node_ids[fn_name] = fn_node_id
                if parent_cls:
                    symbol_node_ids[f"{parent_cls}.{fn_name}"] = fn_node_id

                graph.add_node(GraphNode(
                    id=fn_node_id,
                    type=sym_type,
                    name=fn_name,
                    file_path=path,
                    start_line=fn.get("start_line"),
                    end_line=fn.get("end_line"),
                    metadata={
                        "parent_symbol": parent_cls,
                        "params": fn.get("params", []),
                        "calls": fn.get("calls", []),
                        "docstring": fn.get("docstring", "")
                    }
                ))

                if parent_cls and f"class:{path}:{parent_cls}" in graph.nodes:
                    # Class CONTAINS method
                    graph.add_edge(GraphEdge(
                        source_id=f"class:{path}:{parent_cls}",
                        target_id=fn_node_id,
                        type="CONTAINS"
                    ))
                else:
                    # File CONTAINS function
                    graph.add_edge(GraphEdge(
                        source_id=file_node_id,
                        target_id=fn_node_id,
                        type="CONTAINS"
                    ))

            # C. Variables / Constants
            for var in parsed.get("variables", []):
                var_name = var["name"]
                var_node_id = f"var:{path}:{var_name}"
                graph.add_node(GraphNode(
                    id=var_node_id,
                    type="variable",
                    name=var_name,
                    file_path=path,
                    start_line=var.get("start_line"),
                    end_line=var.get("end_line"),
                    metadata={"var_type": var.get("type", "variable")}
                ))
                graph.add_edge(GraphEdge(
                    source_id=file_node_id,
                    target_id=var_node_id,
                    type="CONTAINS"
                ))

        # 3. Second pass: link EXTENDS, CALLS, and IMPORTS
        for idx, file in enumerate(files_data):
            path = file["path"]
            file_node_id = file_node_ids[path]
            parsed = all_parsed_list[idx]

            # A. Inheritance (EXTENDS)
            for cls in parsed.get("classes", []):
                cls_node_id = f"class:{path}:{cls['name']}"
                for base in cls.get("bases", []):
                    target_base_id = symbol_node_ids.get(base)
                    if target_base_id:
                        graph.add_edge(GraphEdge(
                            source_id=cls_node_id,
                            target_id=target_base_id,
                            type="EXTENDS"
                        ))
                    else:
                        ext_base_id = f"external_class:{base}"
                        if ext_base_id not in graph.nodes:
                            graph.add_node(GraphNode(id=ext_base_id, type="class", name=base, metadata={"external": True}))
                        graph.add_edge(GraphEdge(
                            source_id=cls_node_id,
                            target_id=ext_base_id,
                            type="EXTENDS"
                        ))

            # B. Function Calls (CALLS)
            for fn in parsed.get("functions", []):
                parent_cls = fn.get("parent_symbol")
                sym_type = fn.get("symbol_type", "function")
                fn_node_id = f"{sym_type}:{path}:{parent_cls or 'top'}:{fn['name']}"

                for callee in fn.get("calls", []):
                    callee_node_id = symbol_node_ids.get(callee)
                    if callee_node_id and callee_node_id != fn_node_id:
                        graph.add_edge(GraphEdge(
                            source_id=fn_node_id,
                            target_id=callee_node_id,
                            type="CALLS"
                        ))

            # C. Imports (IMPORTS / DEPENDS_ON)
            # Combine raw imports and dependencies
            all_imported_targets = set()
            for dep in parsed.get("dependencies", []):
                all_imported_targets.add(dep)

            for imp_item in parsed.get("imports", []):
                imp_str = imp_item if isinstance(imp_item, str) else imp_item.get("statement", "")
                # Extract module paths (e.g. from services.auth import ... -> services/auth)
                from_m = re.search(r'from\s+([.\w\/-]+)', imp_str)
                imp_m = re.search(r'import\s+([.\w\/-]+)', imp_str)
                req_m = re.search(r'require\s*\(\s*[\'"]([.\w\/-]+)[\'"]\s*\)', imp_str)
                if from_m:
                    all_imported_targets.add(from_m.group(1))
                if imp_m:
                    all_imported_targets.add(imp_m.group(1))
                if req_m:
                    all_imported_targets.add(req_m.group(1))

            for dep in all_imported_targets:
                dep_normalized = dep.strip("./\\").replace(".", "/")
                matching_internal_file = None

                for other_path in file_node_ids:
                    other_clean = os.path.splitext(other_path)[0]
                    if dep_normalized == other_clean or dep_normalized.endswith(other_clean) or other_clean.endswith(dep_normalized):
                        matching_internal_file = file_node_ids[other_path]
                        break

                if matching_internal_file and matching_internal_file != file_node_id:
                    graph.add_edge(GraphEdge(
                        source_id=file_node_id,
                        target_id=matching_internal_file,
                        type="IMPORTS",
                        metadata={"module": dep}
                    ))
                else:
                    dep_node_id = f"pkg:{dep.split('.')[0].split('/')[0]}"
                    if dep_node_id not in graph.nodes:
                        graph.add_node(GraphNode(id=dep_node_id, type="module", name=dep, metadata={"external": True}))
                    graph.add_edge(GraphEdge(
                        source_id=file_node_id,
                        target_id=dep_node_id,
                        type="DEPENDS_ON",
                        metadata={"package": dep}
                    ))

        # Cache graph in memory
        self._cache[repo_id] = graph
        return graph

    # ================= QUERY METHODS =================
    def get_symbol_relationships(self, symbol_name: str, repository_id: str) -> Dict[str, Any]:
        """
        Finds containing parent, base classes, methods, functions called, and callers of a symbol.
        """
        graph = self.get_graph(repository_id)
        s_key = symbol_name.lower().strip()
        matched_node_ids = graph.symbol_to_nodes.get(s_key, set())

        if not matched_node_ids:
            # Fallback prefix / partial search
            matched_node_ids = {
                nid for s, nids in graph.symbol_to_nodes.items()
                if s_key in s or s in s_key
                for nid in nids
            }

        if not matched_node_ids:
            return {
                "symbol": symbol_name,
                "found": False,
                "message": f"Symbol '{symbol_name}' not found in repository knowledge graph."
            }

        # Deterministic sorting: Class/Interface nodes first, then function/method/variable
        def _node_priority(nid: str):
            node = graph.nodes.get(nid)
            t_prio = {"class": 0, "interface": 1, "function": 2, "method": 3, "module": 4, "variable": 5}
            return (t_prio.get(node.type if node else "", 9), nid)

        sorted_matched_ids = sorted(list(matched_node_ids), key=_node_priority)

        results = []
        for nid in sorted_matched_ids:
            node = graph.nodes.get(nid)
            if not node:
                continue

            # Outgoing relations (calls, extends, contains)
            calls = [graph.nodes[e.target_id].name for e in graph.out_edges.get(nid, []) if e.type == "CALLS" and e.target_id in graph.nodes]
            extends = [graph.nodes[e.target_id].name for e in graph.out_edges.get(nid, []) if e.type == "EXTENDS" and e.target_id in graph.nodes]
            if node.metadata.get("bases"):
                for b in node.metadata["bases"]:
                    if b not in extends:
                        extends.append(b)

            contains = [f"{graph.nodes[e.target_id].name} ({graph.nodes[e.target_id].type})" for e in graph.out_edges.get(nid, []) if e.type == "CONTAINS" and e.target_id in graph.nodes]

            # Incoming relations (called by, parent container)
            called_by = [
                f"{graph.nodes[e.source_id].name} in {graph.nodes[e.source_id].file_path or 'unknown'}"
                for e in graph.in_edges.get(nid, [])
                if e.type == "CALLS" and e.source_id in graph.nodes
            ]
            parents = [
                f"{graph.nodes[e.source_id].name} ({graph.nodes[e.source_id].type})"
                for e in graph.in_edges.get(nid, [])
                if e.type == "CONTAINS" and e.source_id in graph.nodes
            ]

            results.append({
                "name": node.name,
                "type": node.type,
                "file_path": node.file_path,
                "lines": f"{node.start_line}-{node.end_line}" if node.start_line else "unknown",
                "parent_container": parents[0] if parents else None,
                "extends": extends,
                "calls": list(dict.fromkeys(calls)),
                "called_by": list(dict.fromkeys(called_by)),
                "contains": contains[:15]
            })

        return {
            "symbol": symbol_name,
            "found": True,
            "matches": results
        }

    def find_symbol_usages(self, symbol_name: str, repository_id: str) -> Dict[str, Any]:
        """
        Locates all callers, references, and containing locations of a symbol across the repo.
        """
        graph = self.get_graph(repository_id)
        s_key = symbol_name.lower().strip()
        matched_node_ids = graph.symbol_to_nodes.get(s_key, set())

        usages = []
        for nid in matched_node_ids:
            target_node = graph.nodes[nid]
            for edge in graph.in_edges.get(nid, []):
                source_node = graph.nodes.get(edge.source_id)
                if source_node:
                    usages.append({
                        "usage_type": edge.type,
                        "caller_name": source_node.name,
                        "caller_type": source_node.type,
                        "file_path": source_node.file_path,
                        "start_line": source_node.start_line,
                        "end_line": source_node.end_line
                    })

        return {
            "symbol": symbol_name,
            "total_usages": len(usages),
            "usages": usages
        }

    def get_file_dependencies(self, file_path: str, repository_id: str) -> Dict[str, Any]:
        """
        Lists files/packages imported by this file, and files in the repository that import this file.
        """
        graph = self.get_graph(repository_id)
        file_node_id = f"file:{file_path}"
        if file_node_id not in graph.nodes:
            # Match by basename fallback
            matching = [n for n in graph.nodes.values() if n.type == "file" and (n.file_path == file_path or os.path.basename(n.file_path or "") == os.path.basename(file_path))]
            if matching:
                file_node_id = matching[0].id

        if file_node_id not in graph.nodes:
            return {
                "file_path": file_path,
                "found": False,
                "message": f"File '{file_path}' not found in knowledge graph."
            }

        # Outgoing imports
        imports = []
        external_deps = []
        for edge in graph.out_edges.get(file_node_id, []):
            if edge.type == "IMPORTS" and edge.target_id in graph.nodes:
                imports.append(graph.nodes[edge.target_id].file_path or graph.nodes[edge.target_id].name)
            elif edge.type == "DEPENDS_ON" and edge.target_id in graph.nodes:
                external_deps.append(graph.nodes[edge.target_id].name)

        # Incoming imports (files importing this file)
        imported_by = []
        for edge in graph.in_edges.get(file_node_id, []):
            if edge.type == "IMPORTS" and edge.source_id in graph.nodes:
                imported_by.append(graph.nodes[edge.source_id].file_path or graph.nodes[edge.source_id].name)

        return {
            "file_path": file_path,
            "found": True,
            "internal_imports": list(dict.fromkeys(imports)),
            "imported_by_files": list(dict.fromkeys(imported_by)),
            "external_packages": list(dict.fromkeys(external_deps))
        }

    def get_impact_analysis(self, target: str, repository_id: str) -> Dict[str, Any]:
        """
        Calculates blast radius if a function, class, or file is modified.
        Traverses callers, inheritance, dependencies, and downstream importing files.
        """
        graph = self.get_graph(repository_id)
        affected_symbols = set()
        affected_files = set()
        direct_callers = set()
        direct_dependencies = set()

        # Check if target is a file
        file_node_id = f"file:{target}"
        if file_node_id in graph.nodes:
            # Downstream files importing this file
            for edge in graph.in_edges.get(file_node_id, []):
                if edge.type == "IMPORTS" and edge.source_id in graph.nodes:
                    source_node = graph.nodes[edge.source_id]
                    if source_node.file_path:
                        affected_files.add(source_node.file_path)

            # Dependencies imported by target file
            for edge in graph.out_edges.get(file_node_id, []):
                if edge.target_id in graph.nodes:
                    tgt_node = graph.nodes[edge.target_id]
                    direct_dependencies.add(tgt_node.file_path or tgt_node.name)
        else:
            # Target is a symbol
            s_key = target.lower().strip()
            matched_node_ids = graph.symbol_to_nodes.get(s_key, set())
            visited = set()
            queue = list(matched_node_ids)

            # Extract outgoing dependencies for target symbol
            for nid in matched_node_ids:
                for edge in graph.out_edges.get(nid, []):
                    if edge.target_id in graph.nodes:
                        tgt_node = graph.nodes[edge.target_id]
                        direct_dependencies.add(f"{tgt_node.name} ({tgt_node.type})")

            while queue:
                current_id = queue.pop(0)
                if current_id in visited:
                    continue
                visited.add(current_id)

                for edge in graph.in_edges.get(current_id, []):
                    if edge.type in ("CALLS", "EXTENDS") and edge.source_id in graph.nodes:
                        source_node = graph.nodes[edge.source_id]
                        caller_label = f"{source_node.name} ({source_node.type}) in {source_node.file_path or 'unknown'}"
                        affected_symbols.add(caller_label)
                        if edge.source_id in matched_node_ids or current_id in matched_node_ids:
                            direct_callers.add(caller_label)
                        if source_node.file_path:
                            affected_files.add(source_node.file_path)
                        queue.append(edge.source_id)

        affected_syms_list = sorted(list(affected_symbols))
        affected_files_list = sorted(list(affected_files))
        direct_callers_list = sorted(list(direct_callers))
        dependencies_list = sorted(list(direct_dependencies))

        # Calculate blast radius score (0 to 100)
        blast_score = min(100, (len(affected_symbols) * 15) + (len(affected_files) * 20))
        risk_level = "High" if blast_score >= 60 else "Medium" if blast_score >= 25 else "Low"

        return {
            "target": target,
            "impact_risk": risk_level,
            "blast_radius_score": blast_score,
            "affected_symbols_count": len(affected_symbols),
            "affected_files_count": len(affected_files),
            "directly_affected_symbols": direct_callers_list[:15] or affected_syms_list[:15],
            "dependent_files": affected_files_list[:15],
            "callers": direct_callers_list[:15] or affected_syms_list[:15],
            "dependencies": dependencies_list[:15],
            "affected_symbols": affected_syms_list[:20],
            "affected_files": affected_files_list[:20],
            "limitations_notice": (
                "Static graph traversal analysis. Dynamic runtime reflection, duck-typing, "
                "or framework dependency injection may introduce unmapped runtime dependencies."
            )
        }



knowledge_graph_service = KnowledgeGraphService()

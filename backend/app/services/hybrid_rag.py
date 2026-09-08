import re
from typing import List, Dict, Any, Optional
from app.services.vector_db import qdrant_service
from app.services.knowledge_graph import knowledge_graph_service


class HybridRAGService:
    """
    Hybrid Retrieval Engine combining Qdrant semantic vector search with
    Code Knowledge Graph structural traversals.
    """
    def retrieve_hybrid_context(
        self,
        query: str,
        repository_id: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Executes hybrid retrieval:
        1. Vector search for semantically relevant code chunks.
        2. Knowledge graph expansion for caller/callee, class hierarchy, and dependency relationships.
        3. Deduplicates and compiles a comprehensive context block for LLM inference.
        """
        # 1. Semantic Vector Search
        vector_hits = qdrant_service.search_similar_chunks(query, repository_id, limit=limit)

        # 2. Extract entities and symbols mentioned in query or retrieved chunks
        query_tokens = set(re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', query))
        retrieved_symbols = set()
        retrieved_files = set()

        for hit in vector_hits:
            if hit.get("symbol_name"):
                retrieved_symbols.add(hit["symbol_name"])
            if hit.get("file_path"):
                retrieved_files.add(hit["file_path"])

        # Add candidate symbols from query tokens
        for token in query_tokens:
            if len(token) > 3 and not token.lower() in ("this", "what", "which", "where", "with", "from", "that", "code", "file", "function", "class"):
                retrieved_symbols.add(token)

        # 3. Knowledge Graph Expansion
        graph_relationships = []
        seen_relations = set()

        for sym in list(retrieved_symbols)[:6]:
            rel = knowledge_graph_service.get_symbol_relationships(sym, repository_id)
            if rel.get("found") and rel.get("matches"):
                for m in rel["matches"]:
                    rel_key = f"{m['name']}:{m['file_path']}"
                    if rel_key not in seen_relations:
                        seen_relations.add(rel_key)
                        notes = []
                        if m.get("parent_container"):
                            notes.append(f"Contained in: {m['parent_container']}")
                        if m.get("extends"):
                            notes.append(f"Extends: {', '.join(m['extends'])}")
                        if m.get("calls"):
                            notes.append(f"Calls: {', '.join(m['calls'][:5])}")
                        if m.get("called_by"):
                            notes.append(f"Called by: {', '.join(m['called_by'][:5])}")
                        if m.get("contains"):
                            notes.append(f"Contains: {', '.join(m['contains'][:5])}")

                        if notes:
                            graph_relationships.append(
                                f"- **{m['name']}** ({m['type']}) in `{m['file_path']}` (Lines {m['lines']}): {' | '.join(notes)}"
                            )

        # File dependency expansion
        file_deps = []
        for fp in list(retrieved_files)[:3]:
            dep_info = knowledge_graph_service.get_file_dependencies(fp, repository_id)
            if dep_info.get("found"):
                parts = []
                if dep_info.get("internal_imports"):
                    parts.append(f"Imports: {', '.join(dep_info['internal_imports'][:3])}")
                if dep_info.get("imported_by_files"):
                    parts.append(f"Imported by: {', '.join(dep_info['imported_by_files'][:3])}")
                if parts:
                    file_deps.append(f"- `{fp}`: {' | '.join(parts)}")

        # 4. Compile Structured Context
        code_blocks = []
        citations = []
        seen_chunks = set()

        for idx, hit in enumerate(vector_hits):
            chunk_key = f"{hit['file_path']}:{hit['start_line']}-{hit['end_line']}"
            if chunk_key in seen_chunks:
                continue
            seen_chunks.add(chunk_key)

            sym_header = f" [{hit['symbol_type'].upper()}: {hit['symbol_name']}]" if hit.get("symbol_name") else ""
            parent_hdr = f" (in class {hit['parent_symbol']})" if hit.get("parent_symbol") else ""

            code_blocks.append(
                f"### Segment {len(code_blocks)+1}: `{hit['file_path']}`{sym_header}{parent_hdr} (Lines {hit['start_line']}-{hit['end_line']})\n"
                f"```\n{hit['content'][:1200]}\n```"
            )

            citations.append({
                "file_path": hit["file_path"],
                "symbol_name": hit.get("symbol_name"),
                "symbol_type": hit.get("symbol_type"),
                "start_line": hit["start_line"],
                "end_line": hit["end_line"]
            })

        # Assemble unified text block
        sections = []
        if code_blocks:
            sections.append("## Relevant Code Snippets (Semantic Vector Search)\n" + "\n\n".join(code_blocks))

        if graph_relationships:
            sections.append("## Structural Code Knowledge Graph\n" + "\n".join(graph_relationships[:10]))

        if file_deps:
            sections.append("## File Dependency Graph\n" + "\n".join(file_deps[:6]))

        unified_context = "\n\n---\n\n".join(sections) if sections else "No matching semantic or structural code found."

        return {
            "context": unified_context,
            "citations": citations,
            "vector_hits_count": len(vector_hits),
            "graph_relations_count": len(graph_relationships),
            "file_dependencies_count": len(file_deps)
        }


hybrid_rag_service = HybridRAGService()

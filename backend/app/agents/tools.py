from langchain_core.tools import tool
from app.services.vector_db import qdrant_service
from app.database import SessionLocal
from app.models.models import RepositoryFile, CodeChunk, GeneratedDocumentation
from typing import List, Dict, Any, Optional


@tool
def search_codebase(query: str, repository_id: str) -> str:
    """
    Search the repository codebase for code snippets, symbols, and logical structures using semantic vector search.
    Returns matched functions, classes, methods, and modules with structural relationship metadata.
    """
    results = qdrant_service.search_similar_chunks(query, repository_id, limit=5)
    if not results:
        return "No matching code snippets or symbols found in the vector database for this repository."

    formatted = []
    for idx, hit in enumerate(results):
        sym_type = hit.get("symbol_type") or hit.get("chunk_type", "module")
        sym_name = hit.get("symbol_name") or ""
        parent = hit.get("parent_symbol")
        rel = hit.get("relationships") or {}

        header_parts = [f"Result {idx + 1} (Score: {hit['score']:.2f})"]
        if sym_name:
            sym_desc = f"Symbol: [{sym_type.upper()}] {sym_name}"
            if parent:
                sym_desc += f" (in class {parent})"
            header_parts.append(sym_desc)

        header_parts.append(f"File: {hit['file_path']} (Lines {hit['start_line']}-{hit['end_line']})")

        rel_notes = []
        if rel.get("calls"):
            rel_notes.append(f"Calls: {', '.join(rel['calls'][:5])}")
        if rel.get("bases"):
            rel_notes.append(f"Extends: {', '.join(rel['bases'])}")
        if rel.get("methods"):
            rel_notes.append(f"Methods: {', '.join(rel['methods'][:6])}")

        if rel_notes:
            header_parts.append("Relationships: " + " | ".join(rel_notes))

        formatted.append("\n".join(header_parts) + f"\nCode:\n```\n{hit['content']}\n```\n")

    return "\n---\n".join(formatted)


@tool
def read_file_content(file_path: str, repository_id: str) -> str:
    """
    Read the complete text content of a specific file inside the repository.
    Use this when you know the exact file path and need to inspect full contents and imports.
    """
    db = SessionLocal()
    try:
        db_file = db.query(RepositoryFile).filter(
            RepositoryFile.repository_id == repository_id,
            RepositoryFile.path == file_path
        ).first()

        if not db_file:
            # Try matching by filename instead of exact path
            db_file = db.query(RepositoryFile).filter(
                RepositoryFile.repository_id == repository_id,
                RepositoryFile.name == file_path
            ).first()

        if not db_file:
            return f"Error: File '{file_path}' not found in this repository."

        return (
            f"File: {db_file.path}\n"
            f"Size: {db_file.size} bytes | Language: {db_file.language}\n"
            f"Content:\n```\n{db_file.content}\n```"
        )
    except Exception as e:
        return f"Error reading file: {str(e)}"
    finally:
        db.close()


@tool
def list_code_symbols(repository_id: str) -> str:
    """
    List all structured classes, methods, and functions parsed across the repository.
    Use this to inspect key components, architecture hierarchy, and entry point symbols.
    """
    db = SessionLocal()
    try:
        chunks = db.query(CodeChunk).join(RepositoryFile).filter(
            RepositoryFile.repository_id == repository_id,
            CodeChunk.chunk_type.in_(["class", "function", "method"])
        ).all()

        if not chunks:
            return "No symbols parsed for this repository yet."

        symbols = []
        for ch in chunks:
            sym_type = ch.chunk_type.upper()
            # Extract symbol name cleanly from chunk_id
            parts = ch.chunk_id.split(f"_{ch.chunk_type}_")
            sym_name = parts[1].split("_")[0] if len(parts) > 1 else ch.chunk_id
            symbols.append(f"- [{sym_type}] {sym_name} in `{ch.file.path}` (Lines {ch.start_line}-{ch.end_line})")

        return "\n".join(symbols[:100])
    except Exception as e:
        return f"Error listing symbols: {str(e)}"
    finally:
        db.close()


@tool
def get_repository_overview(repository_id: str) -> str:
    """
    Retrieve the architectural overview of the repository including total files, languages,
    key entry points, core modules, main classes/functions, and dependencies.
    """
    db = SessionLocal()
    try:
        doc = db.query(GeneratedDocumentation).filter(
            GeneratedDocumentation.repository_id == repository_id,
            GeneratedDocumentation.doc_type == "overview"
        ).first()

        if doc and doc.content:
            return doc.content

        # Fallback: compute on the fly if overview doc isn't saved yet
        files = db.query(RepositoryFile).filter(RepositoryFile.repository_id == repository_id).all()
        if not files:
            return "No repository files found. Ingestion may still be processing."

        files_data = [{"path": f.path, "name": f.name, "language": f.language, "size": f.size, "content": f.content} for f in files]
        from app.services.analysis_service import analysis_service
        summary = analysis_service.generate_repository_summary(files_data)
        return summary["summary_text"]
    except Exception as e:
        return f"Error retrieving repository overview: {str(e)}"
    finally:
        db.close()

from langchain_core.tools import tool
from app.services.vector_db import qdrant_service
from app.database import SessionLocal
from app.models.models import RepositoryFile, CodeChunk
from typing import List, Dict, Any

@tool
def search_codebase(query: str, repository_id: str) -> str:
    """
    Search the repository codebase for code snippets or logical structures using semantic vector search.
    Use this to find relevant functions, classes, and logic snippets related to the query.
    """
    results = qdrant_service.search_similar_chunks(query, repository_id, limit=5)
    if not results:
        return "No matching code snippets found in the vector database."
        
    formatted = []
    for idx, hit in enumerate(results):
        formatted.append(
            f"Result {idx+1} (Score: {hit['score']:.2f}):\n"
            f"File: {hit['file_path']} (Lines {hit['start_line']}-{hit['end_line']})\n"
            f"Type: {hit['chunk_type']}\n"
            f"Code:\n```\n{hit['content']}\n```\n"
        )
    return "\n---\n".join(formatted)

@tool
def read_file_content(file_path: str, repository_id: str) -> str:
    """
    Read the full text content of a specific file inside the repository.
    Use this when you know the exact file path and need to inspect its full contents.
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
            
        return f"File: {db_file.path}\nSize: {db_file.size} bytes\nLanguage: {db_file.language}\nContent:\n```\n{db_file.content}\n```"
    except Exception as e:
        return f"Error reading file: {str(e)}"
    finally:
        db.close()

@tool
def list_code_symbols(repository_id: str) -> str:
    """
    List all classes, structs, and top-level functions parsed in the repository.
    Use this to understand the main entry points, classes, and structural symbols of the project.
    """
    db = SessionLocal()
    try:
        chunks = db.query(CodeChunk).join(RepositoryFile).filter(
            RepositoryFile.repository_id == repository_id,
            CodeChunk.chunk_type.in_(["class", "function"])
        ).all()
        
        if not chunks:
            return "No class or function symbols parsed for this repository."
            
        symbols = []
        for ch in chunks:
            symbols.append(f"- [{ch.chunk_type.upper()}] {ch.chunk_id.split('_')[-3]} in file: {ch.file.path} (Lines {ch.start_line}-{ch.end_line})")
            
        return "\n".join(symbols[:100]) # Cap to 100 symbols to avoid prompt bloat
    except Exception as e:
        return f"Error listing symbols: {str(e)}"
    finally:
        db.close()

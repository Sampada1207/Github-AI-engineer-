import json
from langchain_core.tools import tool
from app.services.vector_db import qdrant_service
from app.services.knowledge_graph import knowledge_graph_service
from app.services.hybrid_rag import hybrid_rag_service
from app.database import SessionLocal
from app.models.models import RepositoryFile, CodeChunk, GeneratedDocumentation
from typing import List, Dict, Any, Optional


@tool
def search_codebase(query: str, repository_id: str) -> str:
    """
    Search the repository codebase using hybrid retrieval (semantic vector search + code knowledge graph).
    Returns relevant code snippets, containing classes, function call chains, and file dependencies.
    """
    result = hybrid_rag_service.retrieve_hybrid_context(query, repository_id, limit=5)
    return result.get("context", "No matching code or relationships found in the repository.")


@tool
def get_symbol_relationships(symbol_name: str, repository_id: str) -> str:
    """
    Retrieve direct relationships for a symbol (class, method, or function) in the knowledge graph:
    - Containing class or module
    - Base classes / interfaces extended
    - Methods / symbols contained
    - Functions / methods called by this symbol
    - Callers that invoke this symbol
    """
    rel = knowledge_graph_service.get_symbol_relationships(symbol_name, repository_id)
    if not rel.get("found"):
        return f"Symbol '{symbol_name}' was not found in the repository knowledge graph."

    output = [f"## Knowledge Graph Relationships for `{symbol_name}`\n"]
    for idx, match in enumerate(rel.get("matches", [])):
        output.append(f"### Match {idx + 1}: **{match['name']}** ({match['type']})")
        output.append(f"- **File**: `{match['file_path']}` (Lines {match['lines']})")
        if match.get("parent_container"):
            output.append(f"- **Contained in**: `{match['parent_container']}`")
        if match.get("extends"):
            output.append(f"- **Extends / Bases**: {', '.join(match['extends'])}")
        if match.get("calls"):
            output.append(f"- **Calls**: {', '.join(match['calls'])}")
        if match.get("called_by"):
            output.append(f"- **Called By**: {', '.join(match['called_by'])}")
        if match.get("contains"):
            output.append(f"- **Contains Members**: {', '.join(match['contains'])}")
        output.append("")

    return "\n".join(output)


@tool
def find_symbol_usages(symbol_name: str, repository_id: str) -> str:
    """
    Locate all callers, references, and usages of a function, class, or method across the entire repository.
    Use this to see where a function is called or where a class is instantiated.
    """
    usages_data = knowledge_graph_service.find_symbol_usages(symbol_name, repository_id)
    usages = usages_data.get("usages", [])
    if not usages:
        return f"No direct usages of '{symbol_name}' were detected in the codebase."

    output = [f"## Usages of `{symbol_name}` ({len(usages)} occurrences found)\n"]
    for idx, u in enumerate(usages):
        output.append(
            f"{idx + 1}. **{u['caller_name']}** ({u['caller_type']}) via `{u['usage_type']}` "
            f"in `{u['file_path']}` (Lines {u['start_line']}-{u['end_line']})"
        )

    return "\n".join(output)


@tool
def get_file_dependencies(file_path: str, repository_id: str) -> str:
    """
    Analyze the dependency graph for a specific file:
    - Internal repository files it imports
    - External packages it depends on
    - Other files in the repository that import this file
    """
    deps = knowledge_graph_service.get_file_dependencies(file_path, repository_id)
    if not deps.get("found"):
        return f"File '{file_path}' was not found in the repository dependency graph."

    output = [f"## Dependency Graph for `{file_path}`\n"]
    if deps.get("internal_imports"):
        output.append("**Internal Files Imported:**")
        for imp in deps["internal_imports"]:
            output.append(f"- `{imp}`")
        output.append("")

    if deps.get("imported_by_files"):
        output.append("**Imported By Other Files in Repository:**")
        for imp_by in deps["imported_by_files"]:
            output.append(f"- `{imp_by}`")
        output.append("")

    if deps.get("external_packages"):
        output.append(f"**External Package Dependencies:** `{', '.join(deps['external_packages'])}`\n")

    return "\n".join(output)


@tool
def get_impact_analysis(target: str, repository_id: str) -> str:
    """
    Perform blast-radius impact analysis for a symbol or file.
    Calculates upstream callers, dependent modules, and files that could be affected if the target is modified.
    """
    impact = knowledge_graph_service.get_impact_analysis(target, repository_id)
    output = [
        f"## Impact Analysis for `{target}`",
        f"- **Risk Level**: {impact['impact_risk']}",
        f"- **Affected Symbols**: {impact['affected_symbols_count']}",
        f"- **Affected Files**: {impact['affected_files_count']}\n"
    ]

    if impact.get("affected_symbols"):
        output.append("**Potentially Affected Symbols (Callers / Subclasses):**")
        for sym in impact["affected_symbols"]:
            output.append(f"- {sym}")
        output.append("")

    if impact.get("affected_files"):
        output.append("**Potentially Affected Files:**")
        for fp in impact["affected_files"]:
            output.append(f"- `{fp}`")

    return "\n".join(output)


@tool
def read_file_content(file_path: str, repository_id: str) -> str:
    """
    Read the complete text content of a specific file inside the repository.
    Use this when you know the exact file path and need to inspect full contents and imports.
    """
    if not file_path or ".." in file_path or file_path.startswith("/") or "\\" in file_path:
        return "Error: Path traversal or invalid file path detected."

    db = SessionLocal()
    try:
        db_file = db.query(RepositoryFile).filter(
            RepositoryFile.repository_id == repository_id,
            RepositoryFile.path == file_path
        ).first()

        if not db_file:
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


@tool
def review_code(repository_id: str, file_path: Optional[str] = None, symbol_name: Optional[str] = None) -> str:
    """
    Perform a repository-aware AI code review of a specific file, class, or function.
    Audits bugs, security vulnerabilities, performance bottlenecks, bad practices, and error handling.
    Includes blast-radius impact analysis.
    """
    from app.services.review_service import ai_code_review_service
    res = ai_code_review_service.review_codebase(
        repository_id=repository_id,
        file_path=file_path,
        symbol_name=symbol_name
    )

    output = [res["overall_summary"], "\n### Detailed Findings\n"]
    if not res.get("findings"):
        output.append("No specific bugs, security flaws, or code smells detected in this target!")
    else:
        for idx, f in enumerate(res["findings"]):
            output.append(
                f"{idx + 1}. **[{f['severity'].upper()} - {f['category']}]** `{f['file']}` (Line {f['line']})\n"
                f"   - **Explanation**: {f['explanation']}\n"
                f"   - **Suggested Fix**: `{f.get('suggested_fix', 'None')}`\n"
            )

    return "\n".join(output)


@tool
def analyze_diff(repository_id: str, base_revision: str = "main", target_revision: str = "HEAD", diff_text: Optional[str] = None) -> str:
    """
    Analyze Git diff / code changes between base_revision and target_revision (or custom diff_text).
    Evaluates changed files, additions/deletions, changed symbols, downstream impact analysis (blast radius),
    and performs AI review findings for bugs, security risks, or breaking changes.
    """
    from app.services.diff_service import git_diff_service
    try:
        review_res = git_diff_service.review_diff(
            repo_id=repository_id,
            base_revision=base_revision,
            target_revision=target_revision,
            diff_text=diff_text
        )
        ai_rev = review_res.get("ai_review", {})
        summary = ai_rev.get("summary", {})
        findings = ai_rev.get("findings", [])
        impact = review_res.get("impact_analysis", {})

        output = [
            f"## Git Diff & Code Change Analysis (`{review_res['base_revision']}` -> `{review_res['target_revision']}`)\n",
            f"- **Files Changed**: {review_res['total_files_changed']} (+{review_res['total_additions']} / -{review_res['total_deletions']})",
            f"- **Changed Symbols**: {', '.join(review_res['changed_symbols']) or 'None detected'}",
            f"- **Blast Radius Impact Risk**: {impact.get('impact_risk', 'Low')} (Blast Radius Score: {impact.get('blast_radius_score', 0)}/100)",
            f"- **Potentially Affected Callers / Subclasses**: {impact.get('affected_symbols_count', 0)} symbols, {impact.get('affected_files_count', 0)} files\n",
            "### AI Review Findings"
        ]

        if not findings:
            output.append("No critical issues, security risks, or breaking bugs detected in this diff!")
        else:
            for idx, f in enumerate(findings):
                output.append(
                    f"{idx + 1}. **[{f.get('severity', 'Medium').upper()} - {f.get('category', 'General')}]** `{f['file']}` ({f.get('line', 'N/A')})\n"
                    f"   - **Finding Type**: {f.get('finding_type', 'issue in changed code')}\n"
                    f"   - **Explanation**: {f['explanation']}\n"
                    f"   - **Suggested Fix**: `{f.get('suggested_fix', 'None')}`\n"
                )

        return "\n".join(output)
    except Exception as e:
        return f"Error analyzing diff: {str(e)}"



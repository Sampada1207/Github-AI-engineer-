import os
from typing import List, Dict, Any, Optional
from app.config import settings

class DocumentationService:
    def __init__(self):
        self.use_llm = bool(settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY)
        self.llm = None
        
        if self.use_llm:
            try:
                from langchain_openai import ChatOpenAI
                self.llm = ChatOpenAI(
                    model="gpt-4o",
                    temperature=0.2,
                    openai_api_key=settings.OPENAI_API_KEY
                )
            except Exception as e:
                print(f"Failed to initialize ChatOpenAI: {e}. Using static documentation fallback.")
                self.use_llm = False

    def generate_documentation(self, doc_type: str, repo_name: str, files_data: List[Dict[str, Any]], parsed_structures: List[Dict[str, Any]]) -> str:
        """
        Generates markdown documentation for the repository.
        Types: 'readme', 'api', 'class', 'function'.
        """
        if self.use_llm:
            try:
                # Prepare a summary of files and code schemas to send to the LLM
                summary = self._prepare_codebase_summary(files_data, parsed_structures)
                prompt = self._get_prompt_for_doc_type(doc_type, repo_name, summary)
                
                response = self.llm.invoke(prompt)
                return response.content
            except Exception as e:
                print(f"LLM doc gen failed: {e}. Falling back to static doc generation.")
                
        # Static Fallback Generation
        return self._generate_static_doc(doc_type, repo_name, files_data, parsed_structures)

    def _prepare_codebase_summary(self, files: List[Dict[str, Any]], structures: List[Dict[str, Any]]) -> str:
        summary_lines = []
        for file, struct in zip(files, structures):
            summary_lines.append(f"File: {file['path']} ({file['language']})")
            if struct.get("classes"):
                classes_list = [c["name"] for c in struct["classes"]]
                summary_lines.append(f"  Classes: {', '.join(classes_list)}")
            if struct.get("functions"):
                funcs_list = [f["name"] for f in struct["functions"]]
                summary_lines.append(f"  Functions: {', '.join(funcs_list)}")
            if struct.get("imports"):
                summary_lines.append(f"  Imports: {', '.join(struct['imports'][:10])}")
        return "\n".join(summary_lines[:50]) # cap to prevent prompt bloat

    def _get_prompt_for_doc_type(self, doc_type: str, repo_name: str, summary: str) -> str:
        prompts = {
            "readme": f"You are a Senior Technical Writer. Generate a comprehensive, professional README.md for the repository '{repo_name}'. Here is the structure and files of the codebase:\n\n{summary}\n\nInclude installation instructions, project structure, usage, and a description of core features.",
            
            "api": f"You are a Senior Developer. Generate clean REST API documentation for the repository '{repo_name}'. Analyze the following files list containing router endpoints:\n\n{summary}\n\nProvide path parameters, request/response bodies, status codes, and usage examples.",
            
            "class": f"You are an Architect. Generate documentation explaining the core Classes/Types defined in the repository '{repo_name}' based on the files summary:\n\n{summary}\n\nExplain class responsibilities, relationships, methods, and properties.",
            
            "function": f"You are a QA Lead. Generate detailed function-level documentation for the repository '{repo_name}'. File summary:\n\n{summary}\n\nProvide explanation of inputs, outputs, exceptions, and side effects of key functions."
        }
        return prompts.get(doc_type.lower(), prompts["readme"])

    def _generate_static_doc(self, doc_type: str, repo_name: str, files_data: List[Dict[str, Any]], parsed_structures: List[Dict[str, Any]]) -> str:
        """Helper to construct rich local markdown documentation without LLM queries."""
        if doc_type == "readme":
            lines = [
                f"# {repo_name}",
                "\nThis documentation was generated automatically by the code analysis platform.",
                "\n## Project Overview",
                "A modular codebase consisting of the following key directories and files.",
                "\n## File Structure",
                "| File Path | Primary Language | Size (Bytes) |",
                "|---|---|---|",
            ]
            for file in files_data[:20]:
                lines.append(f"| `{file['path']}` | {file['language']} | {file['size']} |")
            if len(files_data) > 20:
                lines.append(f"| ... and {len(files_data) - 20} more files | | |")
                
            lines.extend([
                "\n## Getting Started",
                "To get started, follow these instructions:",
                "1. Clone the repository.",
                "2. Ensure you have the corresponding runtimes installed (Node/Python/Go).",
                "3. Install project dependencies.",
                "4. Run the development/build scripts.",
            ])
            return "\n".join(lines)
            
        elif doc_type == "api":
            lines = [
                f"# API Reference - {repo_name}",
                "\nThis document describes the API entry points and files defined in this codebase.",
                "\n## Detected Code Files & Routers",
            ]
            for file, struct in zip(files_data, parsed_structures):
                if any(k in file["path"].lower() for k in ("route", "api", "controller", "endpoint", "views")):
                    lines.append(f"\n### File: `{file['path']}`")
                    if struct.get("functions"):
                        lines.append("Exposes the following functions/handlers:")
                        for func in struct["functions"]:
                            lines.append(f"- `func {func['name']}()` (Line {func['start_line']}-{func['end_line']})")
                    else:
                        lines.append("Module level router configuration.")
            return "\n".join(lines)
            
        elif doc_type == "class":
            lines = [
                f"# Class Documentation - {repo_name}",
                "\nSummary of object structures and classes parsed in the codebase.",
            ]
            has_classes = False
            for file, struct in zip(files_data, parsed_structures):
                if struct.get("classes"):
                    has_classes = True
                    lines.append(f"\n## File: `{file['path']}`")
                    for cls in struct["classes"]:
                        lines.append(f"\n### Class: `{cls['name']}` (Lines {cls['start_line']}-{cls['end_line']})")
                        lines.append("```python")
                        lines.append(cls["content"])
                        lines.append("```")
            if not has_classes:
                lines.append("\nNo classes were detected in the analyzed files.")
            return "\n".join(lines)
            
        else: # function
            lines = [
                f"# Function Directory - {repo_name}",
                "\nListing of core operational functions extracted from the repository files.",
            ]
            has_funcs = False
            for file, struct in zip(files_data, parsed_structures):
                if struct.get("functions"):
                    has_funcs = True
                    lines.append(f"\n## File: `{file['path']}`")
                    for func in struct["functions"][:5]:  # limit to 5 per file to avoid huge output
                        lines.append(f"- **`{func['name']}`** (Lines {func['start_line']} to {func['end_line']})")
            if not has_funcs:
                lines.append("\nNo functions were detected in the analyzed files.")
            return "\n".join(lines)

doc_service = DocumentationService()

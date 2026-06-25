import os
import shutil
import git
from typing import List, Dict, Any

class GitService:
    def clone_repo(self, repo_url: str, dest_dir: str, branch: str = "main") -> str:
        """
        Clones a git repository to the target destination folder.
        If it already exists, removes it first to perform a clean clone.
        """
        if os.path.exists(dest_dir):
            self.clean_repo(dest_dir)
            
        os.makedirs(dest_dir, exist_ok=True)
        
        try:
            # Basic git clone. We can support cloning with depth=1 for speed.
            git.Repo.clone_from(repo_url, dest_dir, branch=branch, depth=1)
            return dest_dir
        except Exception as e:
            # Fallback to cloning without branch specified in case it's not 'main' (e.g. master)
            try:
                git.Repo.clone_from(repo_url, dest_dir, depth=1)
                return dest_dir
            except Exception as inner_e:
                raise Exception(f"Git clone failed: {str(e)} / {str(inner_e)}")

    def clean_repo(self, dest_dir: str):
        """Removes the cloned directory from disk."""
        if os.path.exists(dest_dir):
            try:
                # Handle potential permissions issues on Windows/Mac
                def handle_remove_readonly(func, path, exc):
                    import stat
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                shutil.rmtree(dest_dir, onerror=handle_remove_readonly)
            except Exception as e:
                # Log error but don't crash
                print(f"Error deleting path {dest_dir}: {str(e)}")

    def scan_repository_files(self, dest_dir: str) -> List[Dict[str, Any]]:
        """
        Recursively scans repository files, filtering out binary and ignored paths (.git, node_modules, etc.).
        Returns list of file dictionary items: path, name, language, size, content.
        """
        ignored_dirs = {
            ".git", "node_modules", "venv", ".venv", "env", "__pycache__", 
            "dist", "build", ".next", ".nuxt", "out", "target", "bin", "obj"
        }
        ignored_extensions = {
            ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", 
            ".mp3", ".mp4", ".wav", ".avi", ".mov", ".db", ".sqlite", ".exe", ".dll", 
            ".so", ".dylib", ".woff", ".woff2", ".ttf", ".eot", ".svg", ".pyc"
        }
        
        files_data = []
        
        for root, dirs, files in os.walk(dest_dir):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
            
            for file in files:
                if file.startswith("."):
                    continue
                
                ext = os.path.splitext(file)[1].lower()
                if ext in ignored_extensions:
                    continue
                    
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, dest_dir)
                
                try:
                    size = os.path.getsize(full_path)
                    # Skip extremely large files (>2MB) to prevent OOM
                    if size > 2 * 1024 * 1024:
                        continue
                        
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        
                    language = self.detect_language(file)
                    
                    files_data.append({
                        "path": rel_path,
                        "name": file,
                        "language": language,
                        "size": size,
                        "content": content
                    })
                except Exception as e:
                    print(f"Skipping file {rel_path} due to error: {e}")
                    
        return files_data

    def detect_language(self, filename: str) -> str:
        """Determines the programming language based on the file extension."""
        ext = os.path.splitext(filename)[1].lower()
        mapping = {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "JavaScript React",
            ".ts": "TypeScript",
            ".tsx": "TypeScript React",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".json": "JSON",
            ".md": "Markdown",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".h": "C/C++ Header",
            ".cs": "C#",
            ".sh": "Shell Script",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".toml": "TOML",
            ".sql": "SQL",
            ".graphql": "GraphQL",
            ".dockerfile": "Docker",
            "dockerfile": "Docker"
        }
        return mapping.get(ext, mapping.get(filename.lower(), "Unknown"))

    def calculate_language_stats(self, files: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculates language composition as percentages of total bytes."""
        lang_bytes = {}
        total_bytes = 0
        
        for file in files:
            lang = file["language"]
            size = file["size"]
            lang_bytes[lang] = lang_bytes.get(lang, 0) + size
            total_bytes += size
            
        if total_bytes == 0:
            return {}
            
        stats = {lang: round((size / total_bytes) * 100, 2) for lang, size in lang_bytes.items()}
        # Sort by percentage descending
        return dict(sorted(stats.items(), key=lambda item: item[1], reverse=True))

git_service = GitService()

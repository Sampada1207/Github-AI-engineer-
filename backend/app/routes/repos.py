import os
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.repositories import crud
from app.schemas.schemas import (
    RepositoryCreate, RepositoryResponse, RepositoryDetailResponse, 
    FileContentResponse, RepositoryAnalyzeRequest, RepositoryAnalyzeResponse
)
from app.routes.deps import get_current_user
from app.models.models import User, Repository, RepositoryFile
from app.services.git_service import git_service
from app.services.parser_service import parser_service
from app.services.embedding_service import embedding_service
from app.services.vector_db import qdrant_service
from app.services.analysis_service import analysis_service
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/repositories", tags=["repositories"])

def process_repository_pipeline(repo_id: str):
    """
    Background pipeline performing git cloning, structural parsing,
    semantic vector DB embedding generation, and static quality evaluation.
    """
    db = SessionLocal()
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        db.close()
        return

    repo_dir = os.path.join(os.getcwd(), "backend", "cloned_repos", str(repo.id))
    
    try:
        # Step 1: Clone Repository
        crud.update_repo_status(db, repo_id, "cloning")
        git_service.clone_repo(repo.url, repo_dir, repo.branch)

        # Step 2: Scan Files and Store in database
        crud.update_repo_status(db, repo_id, "parsing")
        files_data = git_service.scan_repository_files(repo_dir)
        
        db_files = []
        parsed_structures = []
        
        for fd in files_data:
            db_file = crud.create_file(
                db=db,
                repository_id=repo_id,
                path=fd["path"],
                name=fd["name"],
                language=fd["language"],
                size=fd["size"],
                content=fd["content"]
            )
            db_files.append(db_file)
            
            # Step 3: AST / Structure parsing
            parsed_data = parser_service.parse_file(fd["content"], fd["path"], fd["language"])
            parsed_structures.append(parsed_data)
            
            # Step 4: Semantic Chunking
            chunks = parser_service.create_semantic_chunks(fd["content"], fd["path"], parsed_data)
            
            # Step 5: Index code chunks locally
            chunk_records = []
            for ch in chunks:
                db_chunk = crud.create_chunk(
                    db=db,
                    file_id=db_file.id,
                    chunk_id=ch["chunk_id"],
                    content=ch["content"],
                    start_line=ch["start_line"],
                    end_line=ch["end_line"],
                    chunk_type=ch["chunk_type"]
                )
                chunk_records.append((db_chunk, ch))

            # Step 6: Generate Embeddings and Index in Qdrant
            # Batch process embeddings
            if chunk_records:
                crud.update_repo_status(db, repo_id, "indexing")
                chunk_contents = [record[1]["content"] for record in chunk_records]
                
                # Generate vectors
                vectors = embedding_service.get_embeddings(chunk_contents)
                
                # Upload to Qdrant
                just_chunks = [record[1] for record in chunk_records]
                vector_ids = qdrant_service.index_chunks(just_chunks, vectors, repo_id)
                
                # Save metadata links
                for (db_chunk, _), vector_id in zip(chunk_records, vector_ids):
                    crud.create_embeddings_metadata(
                        db=db,
                        chunk_id=db_chunk.id,
                        vector_id=vector_id,
                        metadata={"file_path": db_file.path}
                    )

        # Step 7: Run quality calculations and language composition
        lang_stats = git_service.calculate_language_stats(files_data)
        quality_results = analysis_service.analyze_codebase(files_data)
        
        # Save Code Review issues
        crud.create_code_review(
            db=db,
            repository_id=repo_id,
            branch_or_pr=repo.branch,
            code_smells=quality_results["code_smells"],
            duplicate_code=quality_results["duplicate_code"],
            security_risks=quality_results["security_risks"],
            performance_issues=quality_results["performance_issues"]
        )
        
        # Update Repo completion stats
        crud.update_repo_analysis_results(
            db=db,
            repo_id=repo_id,
            language_stats=lang_stats,
            health_score=quality_results["health_score"]
        )
        crud.update_repo_status(db, repo_id, "completed")
        
    except Exception as e:
        print(f"Pipeline error on repo {repo_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        crud.update_repo_status(db, repo_id, "failed", error_message=str(e))
    finally:
        # Clean up local disk cloned repositories to conserve space
        git_service.clean_repo(repo_dir)
        db.close()


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def submit_repository(
    repo_in: RepositoryCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Submits a repository URL to process.
    Initializes status as 'cloning' and starts background ingestion pipeline.
    """
    project = crud.get_project_by_id(db, repo_in.project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this project")
        
    repo = crud.create_repo(db, repo_in)
    
    # Spawn pipeline task
    background_tasks.add_task(process_repository_pipeline, str(repo.id))
    return repo


@router.get("", response_model=List[RepositoryResponse])
def list_repositories(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists repositories in a project workspace or all user repositories."""
    if not project_id:
        projects = crud.get_projects_by_user(db, user_id=current_user.id)
        repos = []
        for p in projects:
            repos.extend(crud.get_repos_by_project(db, p.id))
        return repos

    project = crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return crud.get_repos_by_project(db, project_id)


@router.get("/{repo_id}", response_model=RepositoryDetailResponse)
def read_repository(repo_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetches details of a repository and counts files."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to read this repository")
        
    files_count = len(repo.files)
    
    resp = RepositoryDetailResponse.model_validate(repo)
    resp.files_count = files_count
    return resp


@router.get("/{repo_id}/tree", response_model=List[Dict[str, Any]])
def get_repository_tree(repo_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Constructs a nested directory tree JSON structure representing
    all files parsed in the repository, suitable for Sidebar explorers.
    """
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    files = crud.get_files_by_repo(db, repo_id)
    return build_tree_structure(files)


@router.get("/{repo_id}/files/{file_id}", response_model=FileContentResponse)
def get_file_content(repo_id: str, file_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns the full code content of a repository file."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    file = crud.get_file_by_id(db, file_id)
    if not file or str(file.repository_id) != repo_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    return file


def build_tree_structure(files: List[RepositoryFile]) -> List[Dict[str, Any]]:
    """Helper to convert flat list of file models to recursive tree nodes."""
    root_node = {"name": "root", "type": "directory", "children": {}}
    
    for file in files:
        parts = file.path.split('/')
        current = root_node
        
        for idx, part in enumerate(parts):
            is_file = (idx == len(parts) - 1)
            
            if is_file:
                current["children"][part] = {
                    "id": str(file.id),
                    "name": part,
                    "path": file.path,
                    "type": "file",
                    "language": file.language,
                    "size": file.size
                }
            else:
                if part not in current["children"]:
                    current["children"][part] = {
                        "id": f"dir_{part}_{idx}",
                        "name": part,
                        "path": "/".join(parts[:idx+1]),
                        "type": "directory",
                        "children": {}
                    }
                current = current["children"][part]
                
    # Format recursive dictionary to nested lists
    def dict_to_list(node):
        if "children" in node:
            children_list = []
            for child in node["children"].values():
                children_list.append(dict_to_list(child))
            # Sort folders first, then alphabetically
            children_list.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
            node["children"] = children_list
        return node
        
    formatted_tree = []
    for child in root_node["children"].values():
        formatted_tree.append(dict_to_list(child))
        
    formatted_tree.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
    return formatted_tree


@router.post("/analyze", response_model=RepositoryAnalyzeResponse)
def analyze_repository_synchronously(
    req: RepositoryAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Synchronously clones and parses a repository using tree-sitter.
    Returns: {
        "repository_name": "",
        "languages": [],
        "files": [],
        "classes": [],
        "functions": [],
        "imports": []
    }
    Stores the extracted files, classes, methods, and imports in PostgreSQL.
    """
    # 1. Resolve Project Container
    project_id = req.project_id
    if not project_id:
        existing_projects = crud.get_projects_by_user(db, user_id=current_user.id)
        if existing_projects:
            project_id = existing_projects[0].id
        else:
            from app.schemas.schemas import ProjectCreate
            new_project = crud.create_project(
                db, 
                ProjectCreate(name="Default Workspace", description="Automated Analysis Container"),
                user_id=current_user.id
            )
            project_id = new_project.id
            
    # 2. Setup Repository record
    repo_name = req.url.split("/")[-1].replace(".git", "")
    from app.schemas.schemas import RepositoryCreate
    repo_in = RepositoryCreate(
        url=req.url,
        name=repo_name,
        branch=req.branch or "main",
        project_id=str(project_id)
    )
    repo = crud.create_repo(db, repo_in)
    
    # 3. Clone Repository
    repo_dir = os.path.join(os.getcwd(), "backend", "cloned_repos", str(repo.id))
    try:
        crud.update_repo_status(db, repo.id, "cloning")
        git_service.clone_repo(repo.url, repo_dir, repo.branch)
        
        # 4. Scan Repository Files
        crud.update_repo_status(db, repo.id, "parsing")
        files_data = git_service.scan_repository_files(repo_dir)
        
        languages_set = set()
        files_list = []
        classes_list = []
        functions_list = []
        imports_list = []
        
        # 5. Parse files using AST/Tree-sitter and save to RDBMS (PostgreSQL/SQLite)
        for fd in files_data:
            # Save file to DB
            db_file = crud.create_file(
                db=db,
                repository_id=repo.id,
                path=fd["path"],
                name=fd["name"],
                language=fd["language"],
                size=fd["size"],
                content=fd["content"]
            )
            
            files_list.append(fd["path"])
            if fd["language"] and fd["language"] != "Unknown":
                languages_set.add(fd["language"])
                
            # AST / Tree-sitter parsing
            parsed_data = parser_service.parse_file(fd["content"], fd["path"], fd["language"])
            
            # Save classes
            for cls in parsed_data["classes"]:
                classes_list.append(cls["name"])
                crud.create_chunk(
                    db=db,
                    file_id=db_file.id,
                    chunk_id=f"{fd['path']}_class_{cls['name']}",
                    content=cls["content"],
                    start_line=cls["start_line"],
                    end_line=cls["end_line"],
                    chunk_type="class"
                )
                
            # Save functions / methods
            for func in parsed_data["functions"]:
                functions_list.append(func["name"])
                crud.create_chunk(
                    db=db,
                    file_id=db_file.id,
                    chunk_id=f"{fd['path']}_func_{func['name']}",
                    content=func["content"],
                    start_line=func["start_line"],
                    end_line=func["end_line"],
                    chunk_type="function"
                )
                
            # Save imports
            for imp in parsed_data["imports"]:
                imports_list.append(imp)
                
        # 6. Update language stats & health score
        lang_stats = git_service.calculate_language_stats(files_data)
        quality_results = analysis_service.analyze_codebase(files_data)
        
        crud.update_repo_analysis_results(
            db=db,
            repo_id=repo.id,
            language_stats=lang_stats,
            health_score=quality_results["health_score"]
        )
        crud.update_repo_status(db, repo.id, "completed")
        
        return RepositoryAnalyzeResponse(
            repository_name=repo_name,
            languages=list(languages_set),
            files=files_list,
            classes=list(set(classes_list)),
            functions=list(set(functions_list)),
            imports=list(set(imports_list))
        )
        
    except Exception as e:
        crud.update_repo_status(db, repo.id, "failed", error_message=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Repository analysis failed: {str(e)}"
        )
    finally:
        # Cleanup cloned directories
        git_service.clean_repo(repo_dir)

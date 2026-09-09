from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.repositories import crud
from app.schemas.schemas import (
    GeneratedDocCreate, GeneratedDocResponse,
    GeneratedDiagramCreate, GeneratedDiagramResponse,
    CodeReviewCreate, CodeReviewResponse,
    AICodeReviewRequest, AICodeReviewResponse,
    DiffParseRequest, DiffParseResponse, DiffAnalysisResponse
)
from app.routes.deps import get_current_user
from app.models.models import User
from app.services.doc_service import doc_service
from app.services.diagram_service import diagram_service
from app.services.parser_service import parser_service
from app.services.analysis_service import analysis_service
from app.services.review_service import ai_code_review_service
from app.services.diff_service import git_diff_service
from typing import List

router = APIRouter(prefix="/repositories/{repo_id}", tags=["ai_generators"])

@router.post("/docs", response_model=GeneratedDocResponse)
def generate_repo_docs(repo_id: str, doc_in: GeneratedDocCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Triggers generation of Markdown documentation (README, API, Classes, Functions)."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    # Get files content for generating docs
    db_files = crud.get_files_by_repo(db, repo_id)
    files_data = [{"path": f.path, "name": f.name, "language": f.language, "size": f.size, "content": f.content} for f in db_files]
    parsed_structures = [parser_service.parse_file(f["content"], f["path"], f["language"]) for f in files_data]
    
    content = doc_service.generate_documentation(doc_in.doc_type, repo.name, files_data, parsed_structures)
    
    # Save to db
    db_doc = crud.create_documentation(db, repository_id=repo_id, doc_type=doc_in.doc_type, file_path=doc_in.file_path, content=content)
    return db_doc

@router.get("/docs", response_model=List[GeneratedDocResponse])
def get_repo_docs(repo_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetches previously generated documentation records for the repository."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    return crud.get_docs_by_repo(db, repo_id)


@router.post("/diagrams", response_model=GeneratedDiagramResponse)
def generate_repo_diagram(repo_id: str, diag_in: GeneratedDiagramCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Triggers generation of Mermaid.js architecture, dependency, or module diagram."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    db_files = crud.get_files_by_repo(db, repo_id)
    files_data = [{"path": f.path, "name": f.name, "language": f.language, "size": f.size, "content": f.content} for f in db_files]
    parsed_structures = [parser_service.parse_file(f["content"], f["path"], f["language"]) for f in files_data]
    
    mermaid_code = diagram_service.generate_diagram(diag_in.diagram_type, files_data, parsed_structures)
    
    # Save to db
    db_diag = crud.create_diagram(db, repository_id=repo_id, diagram_type=diag_in.diagram_type, mermaid_code=mermaid_code)
    return db_diag

@router.get("/diagrams", response_model=List[GeneratedDiagramResponse])
def get_repo_diagrams(repo_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetches previously generated diagrams for the repository."""
    repo = crud.get_repo_id(db, repo_id) if hasattr(crud, 'get_repo_id') else crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    return crud.get_diagrams_by_repo(db, repo_id)


@router.post("/reviews", response_model=CodeReviewResponse)
def generate_code_review(repo_id: str, review_in: CodeReviewCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Manually re-runs static analysis audits and returns a fresh code review report."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    db_files = crud.get_files_by_repo(db, repo_id)
    files_data = [{"path": f.path, "name": f.name, "language": f.language, "size": f.size, "content": f.content} for f in db_files]
    
    analysis_results = analysis_service.analyze_codebase(files_data)
    
    db_review = crud.create_code_review(
        db=db,
        repository_id=repo_id,
        branch_or_pr=review_in.branch_or_pr or "main",
        code_smells=analysis_results["code_smells"],
        duplicate_code=analysis_results["duplicate_code"],
        security_risks=analysis_results["security_risks"],
        performance_issues=analysis_results["performance_issues"]
    )
    
    # Update health score of repository
    crud.update_repo_analysis_results(db, repo_id, repo.language_stats or {}, analysis_results["health_score"])
    
    return db_review

@router.get("/reviews", response_model=List[CodeReviewResponse])
def get_repo_reviews(repo_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetches previously compiled code reviews list for the repository."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    return crud.get_reviews_by_repo(db, repo_id)


@router.post("/ai-review", response_model=AICodeReviewResponse)
def perform_ai_code_review(
    repo_id: str,
    review_req: AICodeReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Executes a repository-aware AI Code Review for a specific file, symbol, or code snippet.
    Includes Knowledge Graph blast-radius impact analysis and structured findings.
    """
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this repository")

    db_files = crud.get_files_by_repo(db, repo_id)
    files_data = [{"path": f.path, "name": f.name, "language": f.language, "size": f.size, "content": f.content} for f in db_files]

    result = ai_code_review_service.review_codebase(
        repository_id=repo_id,
        file_path=review_req.file_path,
        symbol_name=review_req.symbol_name,
        code_snippet=review_req.code_snippet,
        files_data=files_data
    )
    return result


@router.post("/diffs/parse", response_model=DiffParseResponse)
def parse_repository_diff(
    repo_id: str,
    diff_req: DiffParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Parses Git diff changes between base and target revisions or raw diff_text."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this repository")

    try:
        res = git_diff_service.get_repository_diff(
            repo_id=repo_id,
            base_revision=diff_req.base_revision or "main",
            target_revision=diff_req.target_revision or "HEAD",
            diff_text=diff_req.diff_text
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/diffs/analyze", response_model=DiffAnalysisResponse)
def analyze_repository_diff(
    repo_id: str,
    diff_req: DiffParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyzes diff impact across the repository's Knowledge Graph and Hybrid RAG."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this repository")

    try:
        res = git_diff_service.review_diff(
            repo_id=repo_id,
            base_revision=diff_req.base_revision or "main",
            target_revision=diff_req.target_revision or "HEAD",
            diff_text=diff_req.diff_text
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/diffs/review", response_model=DiffAnalysisResponse)
def review_repository_diff(
    repo_id: str,
    diff_req: DiffParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Runs repository-aware AI Review on a Git diff between two revisions or custom diff_text."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this repository")

    try:
        db_files = crud.get_files_by_repo(db, repo_id)
        files_data = [{"path": f.path, "name": f.name, "language": f.language, "size": f.size, "content": f.content} for f in db_files]

        res = git_diff_service.review_diff(
            repo_id=repo_id,
            base_revision=diff_req.base_revision or "main",
            target_revision=diff_req.target_revision or "HEAD",
            diff_text=diff_req.diff_text,
            files_data=files_data
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))



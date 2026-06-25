from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.repositories import crud
from app.schemas.schemas import (
    GeneratedDocCreate, GeneratedDocResponse,
    GeneratedDiagramCreate, GeneratedDiagramResponse,
    CodeReviewCreate, CodeReviewResponse
)
from app.routes.deps import get_current_user
from app.models.models import User
from app.services.doc_service import doc_service
from app.services.diagram_service import diagram_service
from app.services.parser_service import parser_service
from app.services.analysis_service import analysis_service
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
    repo = crud.get_repo_by_id(db, repo_id)
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

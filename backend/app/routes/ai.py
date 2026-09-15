from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.repositories import crud
from app.schemas.schemas import (
    GeneratedDocCreate, GeneratedDocResponse,
    GeneratedDiagramCreate, GeneratedDiagramResponse,
    CodeReviewCreate, CodeReviewResponse,
    AICodeReviewRequest, AICodeReviewResponse,
    DiffParseRequest, DiffParseResponse, DiffAnalysisResponse,
    PRReviewRequest, PRInfo, PRReviewResponse
)
from app.routes.deps import get_current_user
from app.models.models import User
from app.services.doc_service import doc_service
from app.services.diagram_service import diagram_service
from app.services.parser_service import parser_service
from app.services.analysis_service import analysis_service
from app.services.review_service import ai_code_review_service
from app.services.diff_service import git_diff_service
from app.services.github_service import github_service
from typing import List, Optional

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


# ================= GITHUB PULL REQUEST INTEGRATION ENDPOINTS =================
@router.post("/pull-requests/{pr_number}/review", response_model=PRReviewResponse)
def review_github_pull_request_by_path(
    repo_id: str,
    pr_number: int,
    github_repo: Optional[str] = None,
    req_body: Optional[PRReviewRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes a GitHub Pull Request by PR number using the Diff Service, Knowledge Graph,
    Hybrid RAG, and AI Code Review pipeline.
    """
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this repository")

    effective_repo_str = (req_body.github_repo if req_body else None) or github_repo or repo.url

    try:
        owner, repo_name = github_service.extract_owner_repo(effective_repo_str)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid GitHub repository identifier: {str(ve)}"
        )

    return _process_pr_review(db=db, repo_id=repo_id, owner=owner, repo_name=repo_name, pr_number=pr_number)


@router.post("/pull-requests/review", response_model=PRReviewResponse)
def review_github_pull_request_by_body(
    repo_id: str,
    req_body: PRReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes a GitHub Pull Request provided in the request body.
    """
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this repository")

    effective_repo_str = req_body.github_repo or repo.url

    try:
        owner, repo_name = github_service.extract_owner_repo(effective_repo_str)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid GitHub repository identifier: {str(ve)}"
        )

    return _process_pr_review(db=db, repo_id=repo_id, owner=owner, repo_name=repo_name, pr_number=req_body.pr_number)


def _process_pr_review(db: Session, repo_id: str, owner: str, repo_name: str, pr_number: int) -> PRReviewResponse:
    if not pr_number or pr_number <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PR number must be a positive integer.")

    try:
        pr_data = github_service.get_pull_request(owner, repo_name, pr_number)
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        elif "forbidden" in err_msg.lower() or "unauthorized" in err_msg.lower() or "rate limit" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        elif "connect" in err_msg.lower() or "failure" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=err_msg)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    try:
        diff_text = github_service.get_pull_request_diff(owner, repo_name, pr_number)
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    # Get repository files for context
    db_files = crud.get_files_by_repo(db, repo_id)
    files_data = [{"path": f.path, "name": f.name, "language": f.language, "size": f.size, "content": f.content} for f in db_files]

    # Execute Diff + KG + AI Code Review pipeline
    if not diff_text or not diff_text.strip():
        diff_review_res = {
            "repository_id": repo_id,
            "base_revision": pr_data["base_ref"],
            "target_revision": pr_data["head_ref"],
            "total_files_changed": 0,
            "total_additions": 0,
            "total_deletions": 0,
            "changed_symbols": [],
            "files": [],
            "impact_analysis": {
                "impact_risk": "Low",
                "blast_radius_score": 0,
                "affected_symbols_count": 0,
                "affected_files_count": 0,
                "affected_symbols": [],
                "affected_files": []
            },
            "ai_review": {
                "summary": {
                    "diff_summary": "No code diff changes detected in this Pull Request.",
                    "findings_count": 0,
                    "severity_breakdown": {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0},
                    "blast_radius_score": 0,
                    "impact_risk": "Low"
                },
                "findings": []
            }
        }
    else:
        diff_review_res = git_diff_service.review_diff(
            repo_id=repo_id,
            base_revision=pr_data["base_ref"],
            target_revision=pr_data["head_ref"],
            diff_text=diff_text,
            files_data=files_data
        )

    ai_review = diff_review_res.get("ai_review") or {}
    raw_findings = ai_review.get("findings") or []
    summary_obj = ai_review.get("summary") or {}
    severity_breakdown = summary_obj.get("severity_breakdown") or {
        "Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0
    }

    # Format Markdown summary for GitHub review output
    github_summary_str = github_service.format_github_review_summary(pr_data, diff_review_res)

    pr_info_model = PRInfo(**pr_data)

    return PRReviewResponse(
        repository_id=repo_id,
        github_repo=f"{owner}/{repo_name}",
        pr_info=pr_info_model,
        total_files_changed=diff_review_res.get("total_files_changed", 0),
        total_additions=diff_review_res.get("total_additions", pr_data.get("additions", 0)),
        total_deletions=diff_review_res.get("total_deletions", pr_data.get("deletions", 0)),
        changed_symbols=diff_review_res.get("changed_symbols", []),
        files=diff_review_res.get("files", []),
        severity_summary=severity_breakdown,
        findings=raw_findings,
        impact_analysis=diff_review_res.get("impact_analysis", {}),
        github_review_summary=github_summary_str
    )




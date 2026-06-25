from sqlalchemy.orm import Session
from app.models.models import (
    User, Project, Repository, RepositoryFile, CodeChunk,
    EmbeddingsMetadata, Chat, Message, GeneratedDocumentation,
    GeneratedDiagram, CodeReview
)
from app.schemas.schemas import UserCreate, ProjectCreate, RepositoryCreate, ChatCreate
from typing import List, Optional, Dict, Any

# ================= USER CRUD =================
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def create_user(db: Session, user_in: UserCreate, hashed_password: str) -> User:
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        role=user_in.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# ================= PROJECT CRUD =================
def get_projects_by_user(db: Session, user_id: str) -> List[Project]:
    return db.query(Project).filter(Project.user_id == user_id).all()

def get_project_by_id(db: Session, project_id: str) -> Optional[Project]:
    return db.query(Project).filter(Project.id == project_id).first()

def create_project(db: Session, project_in: ProjectCreate, user_id: str) -> Project:
    db_project = Project(
        user_id=user_id,
        name=project_in.name,
        description=project_in.description
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id: str) -> bool:
    project = get_project_by_id(db, project_id)
    if project:
        db.delete(project)
        db.commit()
        return True
    return False

# ================= REPOSITORY CRUD =================
def get_repos_by_project(db: Session, project_id: str) -> List[Repository]:
    return db.query(Repository).filter(Repository.project_id == project_id).all()

def get_repo_by_id(db: Session, repo_id: str) -> Optional[Repository]:
    return db.query(Repository).filter(Repository.id == repo_id).first()

def create_repo(db: Session, repo_in: RepositoryCreate) -> Repository:
    db_repo = Repository(
        project_id=repo_in.project_id,
        url=repo_in.url,
        name=repo_in.name,
        branch=repo_in.branch or "main",
        status="cloning",
        health_score=100
    )
    db.add(db_repo)
    db.commit()
    db.refresh(db_repo)
    return db_repo

def update_repo_status(db: Session, repo_id: str, status: str, error_message: Optional[str] = None) -> Optional[Repository]:
    db_repo = get_repo_by_id(db, repo_id)
    if db_repo:
        db_repo.status = status
        if error_message:
            db_repo.error_message = error_message
        db.commit()
        db.refresh(db_repo)
    return db_repo

def update_repo_analysis_results(db: Session, repo_id: str, language_stats: Dict[str, float], health_score: int) -> Optional[Repository]:
    db_repo = get_repo_by_id(db, repo_id)
    if db_repo:
        db_repo.language_stats = language_stats
        db_repo.health_score = health_score
        from datetime import datetime
        db_repo.last_analyzed_at = datetime.utcnow()
        db.commit()
        db.refresh(db_repo)
    return db_repo

def delete_repo(db: Session, repo_id: str) -> bool:
    repo = get_repo_by_id(db, repo_id)
    if repo:
        db.delete(repo)
        db.commit()
        return True
    return False

# ================= FILE CRUD =================
def create_file(db: Session, repository_id: str, path: str, name: str, language: Optional[str], size: int, content: str) -> RepositoryFile:
    db_file = RepositoryFile(
        repository_id=repository_id,
        path=path,
        name=name,
        language=language,
        size=size,
        content=content
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

def get_files_by_repo(db: Session, repository_id: str) -> List[RepositoryFile]:
    return db.query(RepositoryFile).filter(RepositoryFile.repository_id == repository_id).all()

def get_file_by_id(db: Session, file_id: str) -> Optional[RepositoryFile]:
    return db.query(RepositoryFile).filter(RepositoryFile.id == file_id).first()

# ================= CODE CHUNK CRUD =================
def create_chunk(db: Session, file_id: str, chunk_id: str, content: str, start_line: int, end_line: int, chunk_type: str) -> CodeChunk:
    db_chunk = CodeChunk(
        file_id=file_id,
        chunk_id=chunk_id,
        content=content,
        start_line=start_line,
        end_line=end_line,
        chunk_type=chunk_type
    )
    db.add(db_chunk)
    db.commit()
    db.refresh(db_chunk)
    return db_chunk

def create_embeddings_metadata(db: Session, chunk_id: str, vector_id: str, metadata: Dict[str, Any]) -> EmbeddingsMetadata:
    db_meta = EmbeddingsMetadata(
        chunk_id=chunk_id,
        vector_id=vector_id,
        vector_metadata=metadata
    )
    db.add(db_meta)
    db.commit()
    db.refresh(db_meta)
    return db_meta

# ================= CHAT & MESSAGE CRUD =================
def get_chats_by_repo(db: Session, repository_id: str, user_id: str) -> List[Chat]:
    return db.query(Chat).filter(Chat.repository_id == repository_id, Chat.user_id == user_id).all()

def get_chat_by_id(db: Session, chat_id: str) -> Optional[Chat]:
    return db.query(Chat).filter(Chat.id == chat_id).first()

def create_chat(db: Session, chat_in: ChatCreate, user_id: str) -> Chat:
    db_chat = Chat(
        user_id=user_id,
        repository_id=chat_in.repository_id,
        title=chat_in.title
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat

def delete_chat(db: Session, chat_id: str) -> bool:
    chat = get_chat_by_id(db, chat_id)
    if chat:
        db.delete(chat)
        db.commit()
        return True
    return False

def create_message(db: Session, chat_id: str, role: str, content: str, citations: Optional[List[Dict[str, Any]]] = None) -> Message:
    db_msg = Message(
        chat_id=chat_id,
        role=role,
        content=content,
        citations=citations
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    return db_msg

def get_messages_by_chat(db: Session, chat_id: str) -> List[Message]:
    return db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at.asc()).all()

# ================= DOCUMENTATION CRUD =================
def create_documentation(db: Session, repository_id: str, doc_type: str, file_path: Optional[str], content: str) -> GeneratedDocumentation:
    db_doc = GeneratedDocumentation(
        repository_id=repository_id,
        doc_type=doc_type,
        file_path=file_path,
        content=content
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc

def get_docs_by_repo(db: Session, repository_id: str) -> List[GeneratedDocumentation]:
    return db.query(GeneratedDocumentation).filter(GeneratedDocumentation.repository_id == repository_id).all()

# ================= DIAGRAM CRUD =================
def create_diagram(db: Session, repository_id: str, diagram_type: str, mermaid_code: str) -> GeneratedDiagram:
    db_diag = GeneratedDiagram(
        repository_id=repository_id,
        diagram_type=diagram_type,
        mermaid_code=mermaid_code
    )
    db.add(db_diag)
    db.commit()
    db.refresh(db_diag)
    return db_diag

def get_diagrams_by_repo(db: Session, repository_id: str) -> List[GeneratedDiagram]:
    return db.query(GeneratedDiagram).filter(GeneratedDiagram.repository_id == repository_id).all()

# ================= CODE REVIEW CRUD =================
def create_code_review(
    db: Session, repository_id: str, branch_or_pr: str,
    code_smells: List[Dict[str, Any]], duplicate_code: List[Dict[str, Any]],
    security_risks: List[Dict[str, Any]], performance_issues: List[Dict[str, Any]]
) -> CodeReview:
    db_review = CodeReview(
        repository_id=repository_id,
        branch_or_pr=branch_or_pr,
        code_smells=code_smells,
        duplicate_code=duplicate_code,
        security_risks=security_risks,
        performance_issues=performance_issues
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

def get_reviews_by_repo(db: Session, repository_id: str) -> List[CodeReview]:
    return db.query(CodeReview).filter(CodeReview.repository_id == repository_id).order_by(CodeReview.created_at.desc()).all()

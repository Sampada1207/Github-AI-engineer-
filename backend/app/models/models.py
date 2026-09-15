import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

# Helper to use UUID compatible with both SQLite and PostgreSQL
class GUID(String):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise String(36).
    """
    impl = String
    cache_ok = True

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('length', 36)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value

class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="user", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="projects")
    repositories = relationship("Repository", back_populates="project", cascade="all, delete-orphan")


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(500), nullable=False)
    name = Column(String(255), nullable=False)
    branch = Column(String(100), default="main", nullable=False)
    status = Column(String(50), default="cloning", nullable=False)  # cloning, parsing, indexing, completed, failed
    error_message = Column(Text, nullable=True)
    language_stats = Column(JSON, nullable=True)
    health_score = Column(Integer, default=100, nullable=False)
    last_analyzed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="repositories")
    files = relationship("RepositoryFile", back_populates="repository", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="repository", cascade="all, delete-orphan")
    reviews = relationship("CodeReview", back_populates="repository", cascade="all, delete-orphan")
    docs = relationship("GeneratedDocumentation", back_populates="repository", cascade="all, delete-orphan")
    diagrams = relationship("GeneratedDiagram", back_populates="repository", cascade="all, delete-orphan")


class RepositoryFile(Base):
    __tablename__ = "repository_files"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    path = Column(String(1024), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    language = Column(String(50), nullable=True)
    size = Column(Integer, nullable=False)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    repository = relationship("Repository", back_populates="files")
    chunks = relationship("CodeChunk", back_populates="file", cascade="all, delete-orphan")


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(GUID(), ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    chunk_type = Column(String(50), nullable=False)  # class, function, module
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    file = relationship("RepositoryFile", back_populates="chunks")
    embeddings_metadata = relationship("EmbeddingsMetadata", back_populates="chunk", cascade="all, delete-orphan")


class EmbeddingsMetadata(Base):
    __tablename__ = "embeddings_metadata"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    chunk_id = Column(GUID(), ForeignKey("code_chunks.id", ondelete="CASCADE"), nullable=False)
    vector_id = Column(String(255), nullable=False, index=True)
    vector_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    chunk = relationship("CodeChunk", back_populates="embeddings_metadata")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="chats")
    repository = relationship("Repository", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(GUID(), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    chat = relationship("Chat", back_populates="messages")


class GeneratedDocumentation(Base):
    __tablename__ = "generated_documentation"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    doc_type = Column(String(50), nullable=False)  # readme, api, class, function
    file_path = Column(String(1024), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    repository = relationship("Repository", back_populates="docs")


class GeneratedDiagram(Base):
    __tablename__ = "generated_diagrams"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    diagram_type = Column(String(50), nullable=False)  # architecture, dependency, module
    mermaid_code = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    repository = relationship("Repository", back_populates="diagrams")


class CodeReview(Base):
    __tablename__ = "code_reviews"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    branch_or_pr = Column(String(255), default="main", nullable=False)
    code_smells = Column(JSON, nullable=True)
    duplicate_code = Column(JSON, nullable=True)
    security_risks = Column(JSON, nullable=True)
    performance_issues = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    repository = relationship("Repository", back_populates="reviews")


class WebhookEventLog(Base):
    __tablename__ = "webhook_event_logs"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(255), unique=True, index=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    repository = Column(String(255), nullable=False)
    pr_number = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)  # "processed", "ignored", "failed", "dry-run", "disabled"
    summary = Column(Text, nullable=True)
    findings_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


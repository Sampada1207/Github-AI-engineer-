from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ================= USER SCHEMAS =================
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserResponse(UserBase):
    id: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

# ================= PROJECT SCHEMAS =================
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True

# ================= REPOSITORY SCHEMAS =================
class RepositoryBase(BaseModel):
    url: str
    name: str
    branch: Optional[str] = "main"

class RepositoryCreate(RepositoryBase):
    project_id: str

class RepositoryAnalyzeRequest(BaseModel):
    url: str
    branch: Optional[str] = "main"
    project_id: Optional[str] = None

class RepositoryAnalyzeResponse(BaseModel):
    repository_name: str
    languages: List[str]
    files: List[str]
    classes: List[str]
    functions: List[str]
    imports: List[str]


class RepositoryResponse(RepositoryBase):
    id: str
    project_id: str
    status: str
    error_message: Optional[str] = None
    language_stats: Optional[Dict[str, float]] = None
    health_score: int
    last_analyzed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class RepositoryDetailResponse(RepositoryResponse):
    files_count: int = 0

# ================= FILE SCHEMAS =================
class FileNode(BaseModel):
    id: str
    path: str
    name: str
    type: str  # "file" or "directory"
    language: Optional[str] = None
    size: Optional[int] = None
    children: Optional[List['FileNode']] = None

class FileContentResponse(BaseModel):
    id: str
    path: str
    name: str
    language: Optional[str]
    size: int
    content: str

    class Config:
        from_attributes = True

# ================= CHAT SCHEMAS =================
class ChatCreate(BaseModel):
    repository_id: str
    title: str

class ChatResponse(BaseModel):
    id: str
    user_id: str
    repository_id: str
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    citations: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ================= DOCUMENTATION SCHEMAS =================
class GeneratedDocCreate(BaseModel):
    doc_type: str  # readme, api, class, function
    file_path: Optional[str] = None

class GeneratedDocResponse(BaseModel):
    id: str
    repository_id: str
    doc_type: str
    file_path: Optional[str] = None
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

# ================= DIAGRAM SCHEMAS =================
class GeneratedDiagramCreate(BaseModel):
    diagram_type: str  # architecture, dependency, module

class GeneratedDiagramResponse(BaseModel):
    id: str
    repository_id: str
    diagram_type: str
    mermaid_code: str
    created_at: datetime

    class Config:
        from_attributes = True

# ================= CODE REVIEW SCHEMAS =================
class CodeReviewCreate(BaseModel):
    branch_or_pr: Optional[str] = "main"

class CodeReviewResponse(BaseModel):
    id: str
    repository_id: str
    branch_or_pr: str
    code_smells: Optional[List[Dict[str, Any]]] = None
    duplicate_code: Optional[List[Dict[str, Any]]] = None
    security_risks: Optional[List[Dict[str, Any]]] = None
    performance_issues: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ================= AI CODE REVIEW & IMPACT SCHEMAS =================
class AICodeReviewRequest(BaseModel):
    file_path: Optional[str] = None
    symbol_name: Optional[str] = None
    code_snippet: Optional[str] = None

class AICodeReviewFinding(BaseModel):
    severity: str  # "Critical", "High", "Medium", "Low", "Info"
    category: str  # "Bugs", "Security", "Performance", "Maintainability", "Error Handling", "Bad Practices"
    file: str
    line: Optional[Any] = None  # line number or symbol range string
    explanation: str
    suggested_fix: Optional[str] = None

class AICodeReviewResponse(BaseModel):
    repository_id: str
    target: str
    overall_summary: str
    findings: List[AICodeReviewFinding]
    impact_analysis: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ================= GIT DIFF & CHANGE INTELLIGENCE SCHEMAS =================
class DiffParseRequest(BaseModel):
    base_revision: Optional[str] = "main"
    target_revision: Optional[str] = "HEAD"
    diff_text: Optional[str] = None

class DiffFileChange(BaseModel):
    path: str
    change_type: str  # "modified", "added", "deleted"
    additions: int = 0
    deletions: int = 0
    changed_symbols: List[str] = []
    hunks: List[Dict[str, Any]] = []

class DiffParseResponse(BaseModel):
    repository_id: str
    base_revision: str
    target_revision: str
    total_files_changed: int
    total_additions: int
    total_deletions: int
    files: List[DiffFileChange]

class DiffAnalysisResponse(BaseModel):
    repository_id: str
    base_revision: str
    target_revision: str
    total_files_changed: int
    total_additions: int
    total_deletions: int
    changed_symbols: List[str]
    impact_analysis: Dict[str, Any]
    ai_review: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ================= GITHUB PULL REQUEST INTEGRATION SCHEMAS =================
class PRReviewRequest(BaseModel):
    github_repo: Optional[str] = None  # e.g., "owner/repo" or full URL
    pr_number: int

class PRInfo(BaseModel):
    id: Optional[int] = None
    number: int
    title: str
    state: str
    body: Optional[str] = ""
    author: str
    html_url: str
    base_ref: str
    head_ref: str
    draft: bool = False
    merged: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0

class PRReviewResponse(BaseModel):
    repository_id: str
    github_repo: str
    pr_info: PRInfo
    total_files_changed: int
    total_additions: int
    total_deletions: int
    changed_symbols: List[str]
    files: List[DiffFileChange] = []
    severity_summary: Dict[str, int]
    findings: List[AICodeReviewFinding]
    impact_analysis: Dict[str, Any]
    github_review_summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ================= AUTOMATED PR REVIEW & WEBHOOK SCHEMAS =================
class GitHubWebhookEvent(BaseModel):
    event_id: str
    event_type: str
    action: str
    repository: str
    pr_number: int

class AutomatedPRReviewRequest(BaseModel):
    repository_owner: str
    repository_name: str
    pr_number: int
    action: str
    head_sha: Optional[str] = None
    installation_id: Optional[str] = None

class AutomatedPRReviewResponse(BaseModel):
    status: str  # "dry-run", "processed", "ignored", "disabled", "error"
    repository: str
    pull_request_number: int
    action: str
    review_triggered: bool = False
    dry_run: bool = True
    summary: Optional[str] = ""
    findings_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WebhookLogResponse(BaseModel):
    id: str
    event_id: str
    event_type: str
    action: str
    repository: str
    pr_number: int
    status: str
    summary: Optional[str] = ""
    findings_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True





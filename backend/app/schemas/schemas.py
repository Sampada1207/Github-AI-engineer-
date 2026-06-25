from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ================= USER SCHEMAS =================
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    role: Optional[str] = "user"

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

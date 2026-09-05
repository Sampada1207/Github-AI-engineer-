import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.repositories import crud
from app.schemas.schemas import ProjectCreate, ProjectResponse
from app.routes.deps import get_current_user
from app.models.models import User
from app.config import settings
from app.services.git_service import git_service

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("", response_model=List[ProjectResponse])
def read_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lists all projects owned by the active user."""
    return crud.get_projects_by_user(db, user_id=current_user.id)

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project_in: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Creates a new project container."""
    return crud.create_project(db, project_in, user_id=current_user.id)

@router.get("/{project_id}", response_model=ProjectResponse)
def read_project(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieves metadata of a specific project."""
    project = crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this project")
    return project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Deletes a project and all associated repository analysis."""
    project = crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this project")
    
    for repo in project.repositories:
        git_service.clean_repo(git_service.repo_storage_path(str(repo.id)))

    crud.delete_project(db, project_id)
    return

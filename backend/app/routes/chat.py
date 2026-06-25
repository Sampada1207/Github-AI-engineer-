from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.repositories import crud
from app.schemas.schemas import ChatCreate, ChatResponse, MessageCreate, MessageResponse
from app.routes.deps import get_current_user
from app.models.models import User, Chat, Message
from app.agents import chat_agent
from langchain_core.messages import AIMessage, HumanMessage
from typing import List

router = APIRouter(tags=["chat"])

@router.get("/repositories/{repo_id}/chats", response_model=List[ChatResponse])
def read_repo_chats(repo_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieves all chat logs associated with a repository for the user."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    return crud.get_chats_by_repo(db, repository_id=repo_id, user_id=current_user.id)

@router.post("/repositories/{repo_id}/chats", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_repo_chat(repo_id: str, chat_in: ChatCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Creates a new conversational thread for a repository."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    return crud.create_chat(db, chat_in, user_id=current_user.id)

@router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
def read_chat_messages(chat_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieves the dialogue history of a chat thread."""
    chat = crud.get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    return crud.get_messages_by_chat(db, chat_id=chat_id)

@router.post("/chats/{chat_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_chat_message(chat_id: str, msg_in: MessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Sends a message to the AI assistant.
    Gathers dialogue history, calls the LangGraph agent, and records the answer.
    """
    chat = crud.get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    # 1. Save user message to database
    crud.create_message(db, chat_id=chat_id, role="user", content=msg_in.content)
    
    # 2. Get past messages to populate agent memory
    history = crud.get_messages_by_chat(db, chat_id=chat_id)
    
    # Map to LangChain message models
    agent_messages = []
    for msg in history:
        if msg.role == "user":
            agent_messages.append(HumanMessage(content=msg.content))
        else:
            agent_messages.append(AIMessage(content=msg.content))
            
    # 3. Call LangGraph workflow
    state = {
        "messages": agent_messages,
        "repository_id": str(chat.repository_id),
        "current_file_path": None,
        "citations": []
    }
    
    try:
        result = chat_agent.invoke(state)
        # Extract response
        ai_message = result["messages"][-1]
        response_content = ai_message.content
        citations = result.get("citations") or []
    except Exception as e:
        response_content = f"Error in LangGraph Agent execution: {str(e)}"
        citations = []
        
    # 4. Save AI response to DB
    db_response = crud.create_message(
        db=db,
        chat_id=chat_id,
        role="assistant",
        content=response_content,
        citations=citations
    )
    
    return db_response

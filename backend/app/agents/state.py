from typing import List, Optional, Dict, Any, TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # LangGraph message history (accumulates message objects automatically)
    messages: Annotated[List[BaseMessage], add_messages]
    repository_id: str
    current_file_path: Optional[str]
    citations: Optional[List[Dict[str, Any]]]

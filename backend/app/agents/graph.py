import json
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from app.config import settings
from app.agents.state import AgentState
from app.agents.tools import search_codebase, read_file_content, list_code_symbols

# List of tools available
tools_list = [search_codebase, read_file_content, list_code_symbols]
tools_map = {tool.name: tool for tool in tools_list}

def call_model(state: AgentState, config: RunnableConfig):
    """LLM Node - Invokes LLM with bound tools and system directives."""
    messages = state["messages"]
    repository_id = state["repository_id"]
    
    # Construct System prompt
    system_prompt = (
        "You are an expert AI software engineer analyzing a code repository.\n"
        f"The current repository context ID is '{repository_id}'.\n"
        "Use the provided tools to search the codebase, read files, or list symbols to answer the user's question accurately.\n"
        "Always provide file paths, line numbers, and cite the code you inspect in markdown format.\n"
        "Be concise, clear, and direct."
    )
    
    all_messages = [SystemMessage(content=system_prompt)] + list(messages)
    
    # Check for LLM keys
    if settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=settings.OPENAI_API_KEY)
            llm_with_tools = llm.bind_tools(tools_list)
            response = llm_with_tools.invoke(all_messages)
            return {"messages": [response]}
        except Exception as e:
            print(f"Error in LLM invocation: {e}")
            
    # Fallback: Simple keyword Q&A matching if no LLM key is configured
    user_query = messages[-1].content if messages else ""
    return _generate_mock_agent_response(user_query, repository_id)

def _generate_mock_agent_response(query: str, repository_id: str) -> Dict[str, Any]:
    """Fallback agent generator that queries local Qdrant vectors and builds a response."""
    # Perform a local vector query
    results = qdrant_service_search_local(query, repository_id)
    
    if results:
        code_snippets = []
        citations = []
        for hit in results:
            code_snippets.append(
                f"### File: `{hit['file_path']}` (Lines {hit['start_line']}-{hit['end_line']})\n"
                f"```\n{hit['content'][:500]}...\n```"
            )
            citations.append({
                "file_path": hit["file_path"],
                "start_line": hit["start_line"],
                "end_line": hit["end_line"]
            })
            
        snippets_text = "\n\n".join(code_snippets)
        response_text = (
            f"Here are the code segments related to your query '{query}' parsed from local index:\n\n"
            f"{snippets_text}\n\n"
            "*(Note: Provide an OPENAI_API_KEY in the environment settings to enable fully interactive conversation and coding explanations)*"
        )
        msg = AIMessage(content=response_text)
        return {"messages": [msg], "citations": citations}
        
    msg = AIMessage(content="I searched the database but found no matching code snippets for your query. Please check if files have been fully cloned and indexed.")
    return {"messages": [msg], "citations": []}

def qdrant_service_search_local(query: str, repository_id: str) -> List[Dict[str, Any]]:
    """Helper to query Qdrant inside mock agent without throwing import errors."""
    try:
        from app.services.vector_db import qdrant_service
        return qdrant_service.search_similar_chunks(query, repository_id, limit=3)
    except Exception:
        return []

def call_tools(state: AgentState):
    """Tool execution Node - Executes requested tool calls sequentially."""
    messages = state["messages"]
    last_message = messages[-1]
    repository_id = state["repository_id"]
    
    tool_outputs = []
    citations = state.get("citations") or []
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            # Inject repository_id automatically
            tool_args["repository_id"] = repository_id
            
            # Execute
            tool = tools_map.get(tool_name)
            if tool:
                try:
                    result = tool.invoke(tool_args)
                    # If vector search tool, compile citations
                    if tool_name == "search_codebase":
                        # Attempt to load matching details from vector search return string
                        pass
                except Exception as e:
                    result = f"Error executing tool {tool_name}: {str(e)}"
            else:
                result = f"Tool '{tool_name}' not found."
                
            tool_outputs.append(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"],
                    name=tool_name
                )
            )
            
    return {"messages": tool_outputs, "citations": citations}

def route_next(state: AgentState):
    """Conditional router determining whether to invoke tools or stop."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

# Build the Graph
workflow = StateGraph(AgentState)

# Define nodes
workflow.add_node("model", call_model)
workflow.add_node("tools", call_tools)

# Set entry point
workflow.set_entry_point("model")

# Define edges
workflow.add_conditional_edges(
    "model",
    route_next,
    {
        "tools": "tools",
        END: END
    }
)
workflow.add_edge("tools", "model")

# Compile
chat_agent = workflow.compile()

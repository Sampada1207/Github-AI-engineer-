import json
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from app.config import settings
from app.agents.state import AgentState
from app.agents.tools import (
    search_codebase,
    read_file_content,
    list_code_symbols,
    get_repository_overview
)

# List of tools available
tools_list = [search_codebase, read_file_content, list_code_symbols, get_repository_overview]
tools_map = {tool.name: tool for tool in tools_list}


def call_model(state: AgentState, config: RunnableConfig):
    """LLM Node - Invokes LLM with bound tools and system directives."""
    messages = state["messages"]
    repository_id = state["repository_id"]

    # Construct System prompt
    system_prompt = (
        "You are an expert AI software engineer and code intelligence assistant analyzing a software repository.\n"
        f"The active repository context ID is '{repository_id}'.\n\n"
        "You have access to tools that understand code structure, symbols, hierarchy, and relationships:\n"
        "- `get_repository_overview`: Retrieve high-level architecture, primary languages, key files, modules, and dependencies.\n"
        "- `search_codebase`: Find semantically and structurally relevant classes, functions, methods, and modules.\n"
        "- `read_file_content`: Inspect full file implementations, imports, and definitions.\n"
        "- `list_code_symbols`: View all classes, methods, and top-level functions in the project.\n\n"
        "Guidelines:\n"
        "1. For broad repository questions ('how does this repo work?', 'overview'), call `get_repository_overview`.\n"
        "2. When explaining code, explain the structure, containing classes, and function relationships.\n"
        "3. Always cite file paths, symbol names, and line ranges in markdown format.\n"
        "4. Be accurate, concise, and structured."
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

    # Fallback: Keyword Q&A matching if no LLM key is configured
    user_query = messages[-1].content if messages else ""
    return _generate_mock_agent_response(user_query, repository_id)


def _generate_mock_agent_response(query: str, repository_id: str) -> Dict[str, Any]:
    """Fallback agent generator that queries local Qdrant vectors and builds a structured response."""
    # Check if this is an overview query
    query_lower = query.lower()
    if any(k in query_lower for k in ["overview", "architecture", "structure", "summary", "explain this repository", "list its files"]):
        try:
            overview_text = get_repository_overview.invoke({"repository_id": repository_id})
            if overview_text and not overview_text.startswith("Error"):
                msg = AIMessage(content=f"{overview_text}\n\n*(Note: Configure OPENAI_API_KEY for dynamic conversational AI answers)*")
                return {"messages": [msg], "citations": []}
        except Exception:
            pass

    results = qdrant_service_search_local(query, repository_id)

    if results:
        code_snippets = []
        citations = []
        for hit in results:
            sym_desc = f" [{hit.get('symbol_type', 'code').upper()}: {hit.get('symbol_name')}]" if hit.get('symbol_name') else ""
            parent_desc = f" (in class {hit['parent_symbol']})" if hit.get('parent_symbol') else ""

            code_snippets.append(
                f"### File: `{hit['file_path']}`{sym_desc}{parent_desc} (Lines {hit['start_line']}-{hit['end_line']})\n"
                f"```\n{hit['content'][:500]}...\n```"
            )
            citations.append({
                "file_path": hit["file_path"],
                "start_line": hit["start_line"],
                "end_line": hit["end_line"],
                "symbol_name": hit.get("symbol_name"),
                "symbol_type": hit.get("symbol_type")
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

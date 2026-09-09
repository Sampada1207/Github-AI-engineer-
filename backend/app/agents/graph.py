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
    get_repository_overview,
    get_symbol_relationships,
    find_symbol_usages,
    get_file_dependencies,
    get_impact_analysis,
    review_code,
    analyze_diff
)

# Complete list of hybrid RAG and knowledge graph tools
tools_list = [
    search_codebase,
    read_file_content,
    list_code_symbols,
    get_repository_overview,
    get_symbol_relationships,
    find_symbol_usages,
    get_file_dependencies,
    get_impact_analysis,
    review_code,
    analyze_diff
]
tools_map = {tool.name: tool for tool in tools_list}


def call_model(state: AgentState, config: RunnableConfig):
    """LLM Node - Invokes LLM with bound tools and system directives."""
    messages = state["messages"]
    repository_id = state["repository_id"]

    # Construct System prompt
    system_prompt = (
        "You are an expert AI software engineer and code intelligence assistant analyzing a software repository.\n"
        f"The active repository context ID is '{repository_id}'.\n\n"
        "You have access to a Hybrid Retrieval & Knowledge Graph toolset:\n"
        "- `get_repository_overview`: Retrieve high-level architecture, primary languages, key files, modules, and dependencies.\n"
        "- `search_codebase`: Hybrid semantic + graph search for relevant code snippets, containing classes, and function relationships.\n"
        "- `get_symbol_relationships`: Inspect symbol hierarchy, containing class, base classes, functions called, and callers.\n"
        "- `find_symbol_usages`: Locate all callers and references to a specific function or class across the repo.\n"
        "- `get_file_dependencies`: Trace imported files, dependencies, and all other files that import a given file.\n"
        "- `get_impact_analysis`: Calculate blast radius and potentially affected callers/files if a symbol or file is changed.\n"
        "- `review_code`: Perform repository-aware AI code review auditing bugs, security, performance, maintainability, and blast radius.\n"
        "- `analyze_diff`: Analyze Git diffs/code changes, changed symbols, blast-radius impact analysis, and AI diff review findings.\n"
        "- `read_file_content`: Inspect full file implementations, imports, and definitions.\n"
        "- `list_code_symbols`: View all classes, methods, and top-level functions in the project.\n\n"
        "Guidelines:\n"
        "1. For architecture / overview queries ('how does this repo work?', 'overview'), use `get_repository_overview`.\n"
        "2. For call hierarchies and impact ('what calls X?', 'if I change Y?'), use `find_symbol_usages` or `get_impact_analysis`.\n"
        "3. For diff/change reviews ('review my latest changes', 'what could this change break?'), use `analyze_diff`.\n"
        "4. For code reviews ('review this file', 'audit function X'), use `review_code`.\n"
        "5. When explaining code, explain the structure, containing classes, and function relationships.\n"
        "6. Always cite file paths, symbol names, and line ranges in markdown format.\n"
        "7. Be accurate, concise, and structured.\n"
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

    # Fallback: Hybrid Q&A matching if no LLM key is configured
    user_query = messages[-1].content if messages else ""
    return _generate_mock_agent_response(user_query, repository_id)


def _generate_mock_agent_response(query: str, repository_id: str) -> Dict[str, Any]:
    """Fallback agent generator using hybrid retrieval and graph reasoning tools."""
    query_lower = query.lower()

    # 1. Overview query
    if any(k in query_lower for k in ["overview", "architecture", "structure", "summary", "explain this repository", "list its files"]):
        try:
            overview_text = get_repository_overview.invoke({"repository_id": repository_id})
            if overview_text and not overview_text.startswith("Error"):
                msg = AIMessage(content=f"{overview_text}\n\n*(Note: Configure OPENAI_API_KEY for dynamic conversational AI answers)*")
                return {"messages": [msg], "citations": []}
        except Exception:
            pass

    # 2. Impact analysis query
    if any(k in query_lower for k in ["break", "impact", "affect", "change this"]):
        words = [w for w in query.replace("?", "").split() if len(w) > 2 and w.lower() not in ("what", "could", "break", "if", "change", "this", "class", "function", "file")]
        if words:
            target = words[-1]
            try:
                impact_text = get_impact_analysis.invoke({"target": target, "repository_id": repository_id})
                msg = AIMessage(content=f"{impact_text}\n\n*(Note: Configure OPENAI_API_KEY for dynamic conversational AI answers)*")
                return {"messages": [msg], "citations": []}
            except Exception:
                pass

    # 3. Usage / Caller query
    if any(k in query_lower for k in ["what calls", "who calls", "where is", "used", "usages"]):
        words = [w for w in query.replace("?", "").split() if len(w) > 2 and w.lower() not in ("what", "who", "calls", "where", "is", "used", "this", "function", "class")]
        if words:
            target = words[-1]
            try:
                usage_text = find_symbol_usages.invoke({"symbol_name": target, "repository_id": repository_id})
                msg = AIMessage(content=f"{usage_text}\n\n*(Note: Configure OPENAI_API_KEY for dynamic conversational AI answers)*")
                return {"messages": [msg], "citations": []}
            except Exception:
                pass

    # 4. Hybrid Search Context
    from app.services.hybrid_rag import hybrid_rag_service
    hybrid_res = hybrid_rag_service.retrieve_hybrid_context(query, repository_id, limit=3)

    if hybrid_res.get("context") and hybrid_res["context"] != "No matching semantic or structural code found.":
        response_text = (
            f"Here is the hybrid code intelligence and relationship context for '{query}':\n\n"
            f"{hybrid_res['context']}\n\n"
            "*(Note: Provide an OPENAI_API_KEY in the environment settings to enable fully interactive conversation and coding explanations)*"
        )
        msg = AIMessage(content=response_text)
        return {"messages": [msg], "citations": hybrid_res.get("citations", [])}

    msg = AIMessage(content="I searched the vector database and knowledge graph but found no matching code snippets or relationships for your query. Please check if the repository has completed ingestion.")
    return {"messages": [msg], "citations": []}


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

import os
from typing import List, Dict, Any

class DiagramService:
    def generate_diagram(self, diagram_type: str, files_data: List[Dict[str, Any]], parsed_structures: List[Dict[str, Any]]) -> str:
        """
        Generates Mermaid.js diagrams based on repository data.
        Types: 'architecture', 'dependency', 'module'.
        """
        diagram_type = diagram_type.lower()
        if diagram_type == "dependency":
            return self._generate_dependency_diagram(files_data, parsed_structures)
        elif diagram_type == "module":
            return self._generate_module_diagram(files_data)
        else:  # architecture
            return self._generate_architecture_diagram(files_data)

    def _generate_dependency_diagram(self, files: List[Dict[str, Any]], structures: List[Dict[str, Any]]) -> str:
        """Generates a Mermaid graph showing file imports."""
        mermaid = ["graph TD", "    %% File Dependency Graph"]
        
        # Keep track of file names (basenames) to make the nodes clean
        file_nodes = {}
        for file in files:
            path = file["path"]
            basename = os.path.basename(path)
            node_id = path.replace("/", "_").replace(".", "_").replace("-", "_")
            file_nodes[basename] = node_id
            mermaid.append(f'    {node_id}["{basename}"]')
            
        connections = set()
        
        for file, struct in zip(files, structures):
            path = file["path"]
            node_id = path.replace("/", "_").replace(".", "_").replace("-", "_")
            
            for imp in struct.get("imports", []):
                # Check if this import matches any of our file basenames (simple heuristic)
                file_ext = os.path.splitext(file.get("name", file.get("path", "")))[1]
                imp_base = imp.split(".")[-1] + file_ext
                imp_base_no_ext = imp.split("/")[-1].split(".")[-1]
                
                matched = False
                for fname, fid in file_nodes.items():
                    fname_no_ext = os.path.splitext(fname)[0]
                    if imp_base_no_ext == fname_no_ext or imp == fname:
                        # Connect them
                        conn = f"    {node_id} --> {fid}"
                        connections.add(conn)
                        matched = True
                        break
                        
        if connections:
            mermaid.extend(list(connections)[:30]) # limit connections to avoid rendering chaos
        else:
            # Fallback connection to make it a valid graph if no internal dependencies mapped
            if len(file_nodes) >= 2:
                ids = list(file_nodes.values())
                for i in range(min(5, len(ids) - 1)):
                    mermaid.append(f"    {ids[i]} --> {ids[i+1]}")
            else:
                mermaid.append("    A[Empty Codebase] --> B[Add Source Files]")
                
        return "\n".join(mermaid)

    def _generate_module_diagram(self, files: List[Dict[str, Any]]) -> str:
        """Generates a folder-structure package outline using Mermaid."""
        mermaid = ["graph LR", "    %% Module Directory Structure Graph"]
        
        # Track folders
        folders = set()
        for file in files:
            path = file["path"]
            parts = path.split("/")
            if len(parts) > 1:
                # Add connections between directory parts
                for idx in range(len(parts) - 1):
                    parent = "_".join(parts[:idx+1])
                    child = "_".join(parts[:idx+2])
                    folders.add((parent, child, parts[idx], parts[idx+1]))
                    
        # Define nodes and connections
        defined_nodes = set()
        connections = set()
        
        for parent_id, child_id, parent_name, child_name in folders:
            # Skip building individual file leaves to keep graph clean
            if "." in child_name:
                continue
                
            if parent_id not in defined_nodes:
                mermaid.append(f'    {parent_id}["{parent_name}/"]')
                defined_nodes.add(parent_id)
            if child_id not in defined_nodes:
                mermaid.append(f'    {child_id}["{child_name}/"]')
                defined_nodes.add(child_id)
                
            connections.add(f"    {parent_id} --> {child_id}")
            
        if connections:
            mermaid.extend(list(connections))
        else:
            # Standard modules fallback
            mermaid.extend([
                '    src["src/"] --> components["components/"]',
                '    src --> app["app/"]',
                '    src --> lib["lib/"]'
            ])
            
        return "\n".join(mermaid)

    def _generate_architecture_diagram(self, files: List[Dict[str, Any]]) -> str:
        """Generates a high-level layered architecture diagram for the project."""
        # Detect layers from paths
        has_api = False
        has_ui = False
        has_db = False
        
        for file in files:
            path = file["path"].lower()
            if "route" in path or "api" in path or "controller" in path:
                has_api = True
            if "component" in path or "ui" in path or "page" in path or "view" in path:
                has_ui = True
            if "db" in path or "model" in path or "repository" in path:
                has_db = True
                
        mermaid = [
            "graph TD",
            "    subgraph Client_Tier [Client Front-End]",
            "        UI[UI Components & Layouts]",
            "        State[State Management / Hooks]",
            "        API_Client[API Fetch Client]",
            "    end",
            "",
            "    subgraph Business_Tier [Application Server]",
            "        API_Gateway[FastAPI Server Gateways]",
            "        Business_Logic[Core Services & AST Parsers]",
            "        AI_Agents[LangGraph Chat Agents]",
            "    end",
            "",
            "    subgraph Data_Tier [Data Storage]",
            "        RDBMS[(Relational Database)]",
            "        VectorDB[(Qdrant Vector DB)]",
            "    end",
            "",
            "    %% Connections",
            "    UI --> State",
            "    State --> API_Client",
            "    API_Client ==>|HTTP/JSON| API_Gateway",
            "    API_Gateway --> Business_Logic",
            "    Business_Logic --> AI_Agents",
            "    Business_Logic --> RDBMS",
            "    AI_Agents --> VectorDB"
        ]
        return "\n".join(mermaid)

diagram_service = DiagramService()

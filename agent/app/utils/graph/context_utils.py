from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage

from app.core.graph.state.agent_state import AgentDataset, AgentProject

def get_recent_messages(messages: List[BaseMessage], n: int = 5) -> List[BaseMessage]:
    """Returns the last n messages from the history."""
    if not messages:
        return []
    return messages[-n:]

def format_optimized_workspace(
    active_project: Optional[AgentProject],
    active_datasets: Optional[List[AgentDataset]], 
    system_datasets: Optional[List[AgentDataset]]
) -> str:
    """
    Formats the complete workspace context including:
    1. Project Metadata (Name, Description, Biological Context)
    2. Dataset grouping and file metadata pruning.
    """
    blocks = []

    # 1. Project Context
    if active_project:
        p_name = active_project.get("project_name", "Default Project")
        p_desc = active_project.get("description", "No description provided.")
        p_meta = active_project.get("metadata", {})
        
        blocks.append(f"<active_project name='{p_name}'>")
        blocks.append(f"  <description>{p_desc}</description>")
        if p_meta:
            blocks.append(f"  <biological_context>{p_meta}</biological_context>")
        blocks.append("</active_project>")
    else:
        blocks.append("<active_project status='none' />")

    # 2. Dataset Context
    all_datasets = []
    if active_datasets:
        all_datasets.extend(active_datasets)
    if system_datasets:
        all_datasets.extend(system_datasets)

    if not all_datasets:
        blocks.append("<datasets status='empty' />")
    else:
        blocks.append("<datasets>")
        for ds in all_datasets:
            ds_id = ds.get("dataset_id", "unknown")
            ds_name = ds.get("dataset_name", "unnamed")
            ds_source = ds.get("source", "unknown")
            
            blocks.append(f"  <dataset id='{ds_id}' name='{ds_name}' source='{ds_source}'>")
            
            # Genomic Files
            genomic_files = ds.get("genomic_files") or []
            for f in genomic_files:
                f_id = f.get("file_id", "unknown")
                f_name = f.get("file_name", "unknown")
                f_type = f.get("file_type", "unknown")
                blocks.append(f"    <file category='GENOMIC' type='{f_type}' id='{f_id}'>{f_name}</file>")
            
            # Knowledge Files
            knowledge_files = ds.get("knowledge_files") or []
            knowledge_counts = {}
            knowledge_metadata = {}
            
            for f in knowledge_files:
                name = f.get("file_name", "unknown")
                f_id = f.get("file_id", "unknown")
                f_type = f.get("file_type", "unknown")
                
                knowledge_counts[name] = knowledge_counts.get(name, 0) + 1
                if name not in knowledge_metadata:
                    knowledge_metadata[name] = {"id": f_id, "type": f_type}

            for name, count in knowledge_counts.items():
                meta = knowledge_metadata.get(name, {})
                count_str = f" (x{count})" if count > 1 else ""
                blocks.append(f"    <file category='KNOWLEDGE' type='{meta.get('type', 'unknown')}' id='{meta.get('id', 'unknown')}'>{name}{count_str}</file>")
                
            blocks.append("  </dataset>")
        blocks.append("</datasets>")
        
    return "\n".join(blocks)

def format_tools_for_prompt(
    available_tools: Dict[str, BaseTool], 
    include_description: bool = False, 
    include_params: bool = False
) -> str:
    """
    Formats tool descriptions dynamically based on the target agent's needs.
    """
    descriptions = []
    for name, tool in available_tools.items():
        tool_str = f"- {name}"
        
        # 1. Optionally inject Parameters
        if include_params:
            args_schema = getattr(tool, 'args_schema', None)
            if args_schema:
                try:
                    schema = args_schema.model_json_schema()
                    props = schema.get('properties', {})
                    required = schema.get('required', [])
                    
                    params = []
                    for p_name, p_info in props.items():
                        p_type = p_info.get('type', 'any')
                        is_req = "*" if p_name in required else ""
                        params.append(f"{p_name}{is_req}: {p_type}")
                    
                    if params:
                        tool_str += f"({', '.join(params)})"
                except Exception:
                    pass # Fallback to just the name if schema parsing fails
        
        # 2. Optionally inject Descriptions
        if include_description:
            doc = getattr(tool, 'description', "No description available.")
            doc = doc.strip() # Keep full description for detail-oriented agents
                
            tool_str += f": {doc}"
            
        descriptions.append(tool_str)
            
    return "\n".join(descriptions)
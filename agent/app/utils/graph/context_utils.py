from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage, HumanMessage

from app.core.graph.state.agent_state import AgentDataset, AgentProject

def get_recent_messages(messages: List[BaseMessage], last_k_turns: int = 3) -> List[BaseMessage]:
    """
    Returns the last `k` conversational turns from the history.
    A 'turn' is defined as starting from a HumanMessage to the end of the AI's final response,
    including all intermediate tool calls and tool messages.
    """
    if not messages:
        return []

    # Find the indices of all HumanMessages in the history
    human_indices = [i for i, msg in enumerate(messages) if isinstance(msg, HumanMessage)]

    # If there are no human messages (rare), or we want more turns than exist, return everything
    if not human_indices or last_k_turns >= len(human_indices):
        return messages

    # Get the index of the start of the target turn
    # e.g., if last_k_turns=3, we want the 3rd to last HumanMessage
    start_index = human_indices[-last_k_turns]
    
    return messages[start_index:]

def format_optimized_workspace(
    active_project: Optional[AgentProject],
    active_datasets: Optional[List[AgentDataset]], 
    system_datasets: Optional[List[AgentDataset]]
) -> str:
    """
    Formats the complete workspace context including:
    1. Project Metadata
    2. Active Datasets (Detailed - full IDs for user tools)
    3. System Datasets (Summarized - saves tokens)
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

    # 2. Active Datasets (User Data) -> Fully Detailed
    if not active_datasets:
        blocks.append("<active_datasets status='empty' />")
    else:
        blocks.append("<active_datasets>")
        for ds in active_datasets:
            ds_id = ds.get("dataset_id", "unknown")
            ds_name = ds.get("dataset_name", "unnamed")
            blocks.append(f"  <dataset id='{ds_id}' name='{ds_name}' source='USER_WORKSPACE'>")
            
            for f in ds.get("genomic_files", []):
                blocks.append(f"    <file category='GENOMIC' type='{f.get('file_type')}' id='{f.get('file_id')}'>{f.get('file_name')}</file>")
            
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
        blocks.append("</active_datasets>")

    # 3. System Datasets (Admin Data) -> DYNAMIC SUMMARY ONLY
    if system_datasets:
        total_ds = len(system_datasets)
        genome_names = set()
        knowledge_count = 0

        # Dynamically aggregate what exists in the system
        for ds in system_datasets:
            for f in ds.get("genomic_files", []):
                # We only show the name, NOT the ID
                genome_names.add(f.get("file_name", "unknown"))
            knowledge_count += len(ds.get("knowledge_files", []))

        genome_str = ", ".join(genome_names) if genome_names else "None"

        blocks.append("<system_library_summary>")
        blocks.append(f"  The system contains {total_ds} curated public dataset(s).")
        blocks.append(f"  Available Reference Genomes: [{genome_str}]")
        blocks.append(f"  Curated Knowledge Files: {knowledge_count} documents (These are automatically queried via Semantic Search / RAG).")
        blocks.append("  *NOTE*: If you need the exact ID for a system genome to run a bioinformatics tool, use the 'list_genome_files' tool.")
        blocks.append("</system_library_summary>")
        
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
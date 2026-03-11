import os
import time
from typing import List, Optional
import uuid

from fastapi import UploadFile
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.state import CompiledStateGraph

from app.schemas.agent.agent_response import AgentResponse, RAGSourceItem
from app.core.tools.genome_tool import list_genome_files
from app.core.tools.post_tool import create_post, get_user_posts
from app.schemas.agent.agent_request import AgentRequest

class AgentService:
    
    AVAILABLE_TOOLS = {
        "create_post": create_post,
        "get_user_posts": get_user_posts,
        "genome_files": list_genome_files
    }

    async def process_langgraph_chat(
        self, query: str, file: Optional[UploadFile], graph: CompiledStateGraph
    ) -> AgentResponse:
        """Handles file saving, graph execution, and source consolidation."""
        start_time = time.time()
        uploaded_files_meta = []

        # 1. Handle File Upload
        if file:
            temp_dir = "/tmp/sugarcane"
            os.makedirs(temp_dir, exist_ok=True)

            file_id = str(uuid.uuid4())
            safe_filename = f"{file_id}_{file.filename}"
            temp_file_path = os.path.join(temp_dir, safe_filename)
            
            content = await file.read()
            with open(temp_file_path, "wb") as f:
                f.write(content)
            
            filename = file.filename or ""
            extension = f".{filename.split('.')[-1]}".lower()
            
            uploaded_files_meta.append({
                "file_id": file_id,
                "file_name": file.filename,
                "file_path": temp_file_path,
                "file_type": extension.strip("."), 
                "description": "User uploaded file for context."
            })

        # 2. Initial AgentState
        initial_state = {
            "query": query,
            "messages": [], 
            "uploaded_files": uploaded_files_meta, 
            "iteration_count": 0,
            "max_iterations": 3 
        }

        # 3. Execute Graph
        final_state = await graph.ainvoke(initial_state)

        # 4. Consolidate Sources
        raw_sources = final_state.get("sources_used", [])
        consolidated_sources = self._consolidate_sources(raw_sources)

        process_time = time.time() - start_time

        # 5. Build and Return Response
        return AgentResponse(
            answer=final_state.get("final_answer", "No answer generated."),
            rag_sources=consolidated_sources, 
            tool_executions=final_state.get("tool_results", []),
            execution_time=process_time
        )

    def _consolidate_sources(self, raw_sources: list) -> List[RAGSourceItem]:
        """Groups raw chunks by source_file to return a clean summary."""
        unique_sources = {}
        
        for source in raw_sources:
            file_name = source.get("source_file", "Unknown")
            score = source.get("score", 0.0)
            
            if file_name not in unique_sources:
                unique_sources[file_name] = RAGSourceItem(
                    source_file=file_name,
                    chunks_used=1,
                    highest_score=score
                )
            else:
                unique_sources[file_name].chunks_used += 1
                current_max = unique_sources[file_name].highest_score or 0.0
                unique_sources[file_name].highest_score = max(current_max, score)
                
        return list(unique_sources.values())


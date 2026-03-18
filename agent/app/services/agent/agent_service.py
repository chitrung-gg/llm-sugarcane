import os
import time
from typing import List, Optional
import uuid

from fastapi import UploadFile
from langgraph.graph.state import CompiledStateGraph, RunnableConfig
from langchain_core.messages import HumanMessage

from app.schemas.agent.agent_response import AgentResponse, RAGSourceItem
from app.core.tools.genome_tool import list_genome_files
from app.schemas.agent.agent_request import AgentRequest

class AgentService:
    async def process_langgraph_chat(
        self, thread_id: uuid.UUID, query: str, file: Optional[UploadFile], graph: CompiledStateGraph
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
            "messages": [HumanMessage(content=query)], 
            "uploaded_files": uploaded_files_meta, 
            "iteration_count": 0,
            "max_iterations": 3 
        }

        # 3. Configure the checkpointer to load/save to a specific thread
        config: RunnableConfig = {
            "configurable": {
                "thread_id": str(thread_id)
            }
        }
        # 4. Execute Graph with the config
        final_state = await graph.ainvoke(initial_state, config=config)

        # 5. Consolidate Sources
        raw_sources = final_state.get("sources_used", [])
        consolidated_sources = await self._consolidate_sources(raw_sources)
        process_time = time.time() - start_time

        # 6. Build and Return Response
        return AgentResponse(
            thread_id=thread_id,
            answer=final_state.get("final_answer", "No answer generated."),
            rag_sources=consolidated_sources, 
            tool_executions=final_state.get("tool_results", []),
            execution_time=process_time
        )

    async def _consolidate_sources(self, raw_sources: list) -> List[RAGSourceItem]:
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


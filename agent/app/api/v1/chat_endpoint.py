import os
import time
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from langgraph.graph.state import CompiledStateGraph

from app.core.dependencies import get_agent_graph
from app.services.agent.agent_service import AgentService

from app.schemas.agent.agent_request import AgentRequest
from app.schemas.agent.agent_response import AgentResponse
from app.services.llm.llm_service import LLMService


router = APIRouter()

@router.post("/agent_langgraph/chat", response_model=AgentResponse)
async def chat_with_langgraph_agent(
    query: str = Form(..., description="Query"),
    file: Optional[UploadFile] = File(None, description="Optional file for context"),
    graph: CompiledStateGraph = Depends(get_agent_graph)
):
    start_time = time.time()
    temp_file_path = None

    try:
        uploaded_files_meta = []

        if file:
            temp_dir = "/tmp/sugarcane"
            os.makedirs(temp_dir, exist_ok=True)

            # Generate a unique filename to prevent collisions between concurrent users
            file_id = str(uuid.uuid4())
            safe_filename = f"{file_id}_{file.filename}"
            temp_file_path = os.path.join(temp_dir, safe_filename)
            
            # Save the file asynchronously
            content = await file.read()
            with open(temp_file_path, "wb") as f:
                f.write(content)
            
            # Extract the extension (e.g., 'pdf', 'md')

            filename = file.filename or ""
            extension = f".{filename.split('.')[-1]}".lower()
            
            # Construct metadata exactly as your AgentState expects
            uploaded_files_meta.append({
                "file_id": file_id,
                "file_name": file.filename,
                "file_path": temp_file_path,
                "file_type": extension.strip("."), 
                "description": "User uploaded file for context."
            })

        # Initial AgentState
        initial_state = {
            "query": query,
            "messages": [], 
            # If your AgentRequest accepts files, map them here. Otherwise, pass an empty list.
            "uploaded_files": uploaded_files_meta, 
            "iteration_count": 0,
            "max_iterations": 3 # Circuit breaker limit
        }

        # Execute the Graph asynchronously
        final_state = await graph.ainvoke(initial_state)

        # Calculate execution time
        process_time = time.time() - start_time

        # Extract data from the final state to build the response
        # Using .get() ensures it doesn't crash if a branch (like tools) was never executed
        final_answer = final_state.get("final_answer", "No answer generated.")
        rag_results = final_state.get("rag_results", [])
        tool_results = final_state.get("tool_results", [])
        sources_used = final_state.get("sources_used", [])

        # Return the structured response
        return AgentResponse(
            answer=final_answer,
            rag_sources=sources_used,          # Include the exact chunks/papers cited
            tool_executions=tool_results,      # Include BLAST/Synteny statuses and times
            execution_time=process_time
        )
        
    except Exception as e:
        # Log the error internally here if you have a logger
        print(f"Graph Execution Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
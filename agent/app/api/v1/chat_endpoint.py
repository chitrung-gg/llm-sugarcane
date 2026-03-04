import time
from fastapi import APIRouter, Depends, HTTPException

from langgraph.graph.state import CompiledStateGraph

from app.core.dependencies import get_agent_graph
from app.services.agent.agent_service import AgentService

from app.schemas.agent.agent_request import AgentRequest
from app.schemas.agent.agent_response import AgentResponse
from app.services.llm.llm_service import LLMService


router = APIRouter()

@router.post("/agent_langgraph/chat", response_model=AgentResponse)
async def chat_with_langgraph_agent(
    request: AgentRequest,
    graph: CompiledStateGraph = Depends(get_agent_graph)
):
    start_time = time.time()
    
    try:
        # 1. Prepare the initial AgentState
        # We only need to provide the initial inputs. LangGraph will handle the rest.
        initial_state = {
            "query": request.query,
            "messages": [], 
            # If your AgentRequest accepts files, map them here. Otherwise, pass an empty list.
            "uploaded_files": getattr(request, "uploaded_files", []), 
            "iteration_count": 0,
            "max_iterations": 3 # Circuit breaker limit
        }

        # 2. Execute the Graph asynchronously
        # ainvoke() runs the graph until it hits the END node
        final_state = await graph.ainvoke(initial_state)

        # 3. Calculate execution time
        process_time = time.time() - start_time

        # 4. Extract data from the final state to build the response
        # Using .get() ensures it doesn't crash if a branch (like tools) was never executed
        final_answer = final_state.get("final_answer", "No answer generated.")
        rag_results = final_state.get("rag_results", [])
        tool_results = final_state.get("tool_results", [])
        sources_used = final_state.get("sources_used", [])

        # 5. Return the structured response
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
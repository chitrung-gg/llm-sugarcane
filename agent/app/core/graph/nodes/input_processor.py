from agent.app.core.graph.state.agent_state import AgentState
from agent.app.utils.document_processor import DocumentProcessor


async def input_processor(state: AgentState, document_processor: DocumentProcessor):
    """
    Entry node of the graph. Process to provide in-context information for the query
    
    Populates:
    - uploaded_files: with 'parsed_chunks' added for context-only files
    - query: enriched with content from context-only files
    - iteration_count: reset to 0
    - sources_used: initialized as empty list
    """
    parsed_files = []
    context_chunks = []

    for file in state.get("uploaded_files", []):
        file_path = file["file_path"]

        # Inject into the query's context window
        chunks = document_processor.process_and_get_chunks(file_path)
        context_text = "\n\n".join(c.page_content for c in chunks)
        parsed_files.append({
            **file, "parsed_chunks": chunks
        })
        context_chunks.append(f"[Uploaded File: {file['file_name']}]\n{context_text}")

    # Enrich query with any in-context file content
    enriched_query = state["query"]
    if context_chunks:
        files_context = "\n\n---\n\n".join(context_chunks)
        enriched_query = (
            f"{state['query']}\n\n"
            f"### Uploaded Files Context:\n{files_context}"
        )

    return {
        "uploaded_files": parsed_files,
        "query": enriched_query,
        "iteration_count": 0,
        "max_iterations": 5,
        "sources_used": [],
    }

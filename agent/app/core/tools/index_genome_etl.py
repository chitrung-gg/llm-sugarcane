import httpx
from typing import Optional
from langchain_core.tools import tool
from app.core.tools.registry.registry_tool import register_agent_tool
from app.configs.settings.settings import get_settings

@register_agent_tool
@tool
async def index_new_genome(
    s3_uri: str, 
    genome_name: str, 
    file_type: str,
    project_name: Optional[str] = None,
    dataset_name: Optional[str] = None
) -> dict:
    """
    Triggers the backend ETL pipeline to parse, embed, and index a newly uploaded genome file.
    Use this immediately after a user uploads a .fasta or .gff3 file that needs processing.
    
    Args:
        s3_uri: The S3 location of the file.
        genome_name: The display name for this genome.
        file_type: 'fasta' or 'gff3'.
        project_name: The top-level workspace/project name.
        dataset_name: The specific cultivar/dataset name.
    """
    settings = get_settings()
    url = f"{settings.genome_backend_api_url}/api/v1/etl/trigger-genome"
    
    payload = {
        "s3_uri": s3_uri,
        "genome_name": genome_name,
        "file_type": file_type,
        "project_name": project_name,
        "dataset_name": dataset_name
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": "SUCCESS",
                "message": f"Successfully triggered indexing pipeline for {genome_name}.",
                "job_id": data.get("run_id")
            }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Failed to contact the processing server: {str(e)}"
        }
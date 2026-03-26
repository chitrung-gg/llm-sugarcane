import httpx
from langchain_core.tools import tool
from app.configs.settings.settings import get_settings

@tool
async def index_new_genome(s3_uri: str, genome_name: str, file_type: str) -> dict:
    """
    Triggers the backend ETL pipeline to parse, embed, and index a newly uploaded genome file.
    Use this immediately after a user uploads a .fasta or .gff3 file that needs processing.
    """
    settings = get_settings()
    url = f"{settings.genome_backend_api_url}/api/v1/etl/trigger-genome"
    
    payload = {
        "s3_uri": s3_uri,
        "genome_name": genome_name,
        "file_type": file_type
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
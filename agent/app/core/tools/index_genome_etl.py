# import httpx
# import uuid
# from typing import Optional, Dict, Any
# from langchain_core.tools import tool
# from app.core.tools.registry.registry_tool import register_agent_tool
# from app.configs.settings.settings import get_settings

# async def trigger_genome_indexing(
#     genome_global_id: uuid.UUID,
#     genome_name: str, 
#     s3_uri: str, 
#     file_type: str,
#     dataset_id: uuid.UUID,
#     is_public: bool = False,
#     user_id: Optional[uuid.UUID] = None
# ) -> Dict[str, Any]:
#     """Underlying implementation for genome indexing trigger."""
#     settings = get_settings()
#     url = f"{settings.GENOME_BACKEND_API_URL}/api/v1/etl/trigger-genome"
    
#     payload = {
#         "genome_global_id": str(genome_global_id),
#         "genome_name": genome_name,
#         "s3_uri": s3_uri,
#         "file_type": file_type,
#         "dataset_id": str(dataset_id),
#         "is_public": is_public,
#         "user_id": str(user_id) if user_id else None
#     }
    
#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.post(url, json=payload)
#             response.raise_for_status()
#             data = response.json()
            
#             return {
#                 "status": "SUCCESS",
#                 "message": f"Successfully triggered indexing pipeline for {genome_name}.",
#                 "job_id": data.get("run_id")
#             }
#     except Exception as e:
#         return {
#             "status": "ERROR",
#             "message": f"Failed to contact the processing server: {str(e)}"
#         }

# @register_agent_tool
# @tool
# async def index_new_genome(
#     genome_global_id: uuid.UUID, 
#     genome_name: str, 
#     s3_uri: str, 
#     file_type: str,
#     dataset_id: uuid.UUID,
#     is_public: bool = False,
#     user_id: Optional[uuid.UUID] = None
# ) -> dict:
#     """
#         Triggers the backend ETL pipeline to process and index genomic data files from S3.
#         Use this tool after a user uploads a genomic file to RustFS/S3 to make it searchable and 
#         available for bioinformatics analysis (BLAST, Synteny, Primer Design).
        
#         Args:
#             s3_uri: The S3 location of the file (e.g., 's3://bucket/path/file.fasta.gz').
#             genome_name: The display name or variety/cultivar name of the genome.
#             file_type: The semantic type of the file:
#                 - 'genome' or 'assembly': Main genomic sequence (FASTA). Triggers BLAST indexing and N50 analysis.
#                 - 'gff3': Annotation file. Triggers gene feature parsing and semantic extraction for AI search.
#                 - 'cds': Coding sequences (FASTA).
#                 - 'protein': Protein sequences (FASTA).
#                 - 'gene': Gene-specific sequences (FASTA).
#             dataset_id: The unique ID of the Cultivar/Dataset container.
#             is_public: Set to True for system-wide reference genomes, False for private user variants.
#             user_id: The unique ID of the owner. Mandatory if is_public is False.
#     """
#     return await trigger_genome_indexing(
#         genome_global_id=genome_global_id,
#         genome_name=genome_name,
#         s3_uri=s3_uri,
#         file_type=file_type,
#         dataset_id=dataset_id,
#         is_public=is_public,
#         user_id=user_id
#     )

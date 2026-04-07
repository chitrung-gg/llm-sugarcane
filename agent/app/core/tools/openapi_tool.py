from typing import List, Optional
from loguru import logger
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import BaseTool, tool
from langchain_community.agent_toolkits.openapi.spec import reduce_openapi_spec
from langchain_community.agent_toolkits.openapi import planner

import yaml

def build_openapi_tools(
    llm: BaseLanguageModel, 
    openapi_yaml_path: str,
    api_key: Optional[str] = None
) -> List[BaseTool]:
    """
    Creates a single Hierarchical Agent tool that can navigate the OpenAPI Datasets API.
    """
    try:
        # 1. Load the local YAML specification
        with open(openapi_yaml_path, 'r', encoding='utf-8') as f:
            raw_spec = yaml.safe_load(f)

        # This function compresses the spec into a format optimized for LLM consumption
        reduced_spec = reduce_openapi_spec(raw_spec)

        # 2. Setup Request Wrapper
        headers = {"Accept": "application/json"}
        if api_key:
            headers["api-key"] = api_key
        requests_wrapper = TextRequestsWrapper(headers=headers)
        
        # 3. Create the agent
        # allow_dangerous_requests=True is required to allow the agent to execute real HTTP calls.
        NCBI_SUB_AGENT_PROMPT = """
            You are a highly resilient NCBI Datasets API assistant. 
            Your goal is to fetch biological metadata. NEVER give up if a direct search fails.

            CRITICAL API QUIRKS & RULES:
            1. NO SPACES IN URLS: You MUST URL-encode spaces to '%20'.
            
            2. THE "ASSEMBLY NAME" TRAP (IMPORTANT):
               NEVER use `/genome/assembly_name/` unless the user provides a highly specific, formal assembly name (like 'GRCh38' or 'Sugarcane_R570_v1.0'). 
               Casual names like "sugarcane r570" WILL FAIL.

            3. THE "BROAD SEARCH" STRATEGY (MANDATORY FALLBACK):
               If the user asks for a genome using a casual name (e.g., "sugarcane r570", "rice nipponbare"), DO NOT search by assembly name. Instead:
               - Step 1: Extract the core species name (e.g., "sugarcane", "rice", "human").
               - Step 2: Call `GET /genome/taxon/{species}/dataset_report`.
               - Step 3: Read the JSON response and manually search through the records to find the specific strain/cultivar (e.g., look for "r570" in the 'organism' or 'assembly_name' fields).
               - Step 4: Extract the metadata from that specific record.

            Example Workflow for User: "metadata for genome sugarcane r570"
            Action 1: GET /genome/taxon/sugarcane/dataset_report
            Action 2: Scan the returned JSON array. Find the object where cultivar is "R570". 
            Action 3: Return the metadata of that specific object to the user.
        """

        openapi_agent_executor = planner.create_openapi_agent(
            verbose=True,
            prefix=NCBI_SUB_AGENT_PROMPT,
            api_spec=reduced_spec,
            requests_wrapper=requests_wrapper,
            llm=llm,
            allow_dangerous_requests=True
        )

        # 4. Wrap the Sub-Agent in a Tool for the Main Agent
        @tool
        async def query_ncbi_datasets(query: str) -> str:
            """
            Fetches global biological knowledge (genes, genomes, taxonomy) from NCBI.
            Use this ONLY when local search fails. Pass a natural language query.
            Example: 'Search for BRCA1 gene in human' or 'Get summary for accession GCF_000001405.40'
            """
            # The sub-agent handles the multi-turn OpenAPI logic internally
            logger.debug(f"[Sub-Agent] Triggered NCBI Planner for query: {query}")
            
            strict_query = f"""
                Task: {query}
                
                ⚠️ CRITICAL EXECUTION RULES FOR API PLANNER:
                1. FATAL ERROR PREVENTION: You MUST URL-encode all spaces in your API URLs (replace spaces with '%20').
                - WRONG: GET /genome/assembly_name/sugarcane r570/dataset_report
                - CORRECT: GET /genome/assembly_name/sugarcane%20r570/dataset_report
                2. STRATEGY: Do NOT guess assembly names. First, use /taxonomy/name/ to get the TaxID, then use /genome/taxon/{{taxId}}.
            """
            # The sub-agent handles the multi-turn OpenAPI logic internally
            response = await openapi_agent_executor.ainvoke({"input": strict_query})
            return response.get("output", str(response))

        logger.info(f"Successfully initialized OpenAPI Hierarchical Agent from {openapi_yaml_path}")
        return [query_ncbi_datasets]
        
    except Exception as e:
        logger.error(f"Failed to load OpenAPI spec from {openapi_yaml_path}: {e}")
        return []
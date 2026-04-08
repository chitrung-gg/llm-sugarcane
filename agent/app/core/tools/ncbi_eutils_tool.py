from typing import Any, Dict, Optional

import aiohttp
from aiolimiter import AsyncLimiter
from langchain_core.tools import tool
from loguru import logger

from app.configs.settings.settings import get_settings
from app.schemas.tool.ncbi_eutils_tool_schema import GeneSearchArgs, GenomeSearchArgs, PubMedSearchArgs

settings = get_settings()
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DATASETS_BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2"

# Set up the rate limiter
RATE_LIMIT = 10 if settings.ncbi_api_key else 3
limiter = AsyncLimiter(RATE_LIMIT, 1)

@tool(args_schema=PubMedSearchArgs)
async def search_literature_for_traits(organism: str, primary_concept: str, secondary_concept: Optional[str] = None) -> str:
    """
    Search scientific literature (PubMed) to discover which genes control specific traits or diseases.
    
    CRITICAL PROMPT RULES:
    1. USE THIS FIRST: If the user asks about traits, mechanisms, or diseases, use this tool to discover the responsible Gene Symbols.
    2. KEEP IT BROAD: Do not over-constrain the search. It's better to search just 'sugar content' than 'sugar content CRISPR editing'.
    """
    logger.debug(f"[Literature Tool] Organism: {organism} | Primary: {primary_concept} | Secondary: {secondary_concept}")
    
    # Safely format the strict NCBI Boolean query
    query_parts = [f"{organism}[Organism]", f"{primary_concept}[Title/Abstract]"]
    if secondary_concept:
        query_parts.append(f"{secondary_concept}[Title/Abstract]")
        
    entrez_query = " AND ".join(query_parts)
    
    async with aiohttp.ClientSession() as session:
        try:
            search_url = f"{EUTILS_BASE}/esearch.fcgi"
            params = build_eutils_params(db="pubmed", term=entrez_query, retmode="json", retmax=3)
            
            async with limiter:
                async with session.get(search_url, params=params) as resp:
                    if resp.status != 200:
                        raise ValueError(f"PubMed Search failed: {await resp.text()}")
                    search_data = await resp.json()
            
            pmids = search_data.get("esearchresult", {}).get("idlist", [])
            
            # ANTI-LOOP ERROR MESSAGE
            if not pmids:
                return (
                    f"❌ 0 results found for: '{entrez_query}'.\n"
                    f"INSTRUCTION: The search was too strict. Do NOT run multiple variations of this tool. "
                    f"If you used a secondary_concept, try calling this tool exactly ONE MORE TIME using ONLY the primary_concept. "
                    f"If it still fails, move to 'direct_answer' and state the literature is unavailable."
                )

            # Fetch the actual abstracts
            fetch_url = f"{EUTILS_BASE}/efetch.fcgi"
            fetch_params = build_eutils_params(db="pubmed", id=",".join(pmids), retmode="text", rettype="abstract")
            
            async with limiter:
                async with session.get(fetch_url, params=fetch_params) as resp:
                    abstracts = await resp.text()

            return f"✅ FOUND {len(pmids)} RELEVANT ABSTRACTS:\n\n{abstracts}\n\n---\nINSTRUCTION FOR LLM: Read these abstracts to answer the user's question. If you identify specific gene symbols, you can use 'get_gene_metadata_by_symbol' to get more data."

        except Exception as e:
            logger.error(f"[Literature Tool] Error: {str(e)}")
            raise e

@tool(args_schema=GeneSearchArgs)
async def get_gene_metadata_by_symbol(organism: str, gene_symbol: str) -> str:
    """
    Retrieve deep genomic metadata (Chromosome, Gene Ontology, Pathways) for a specific gene OR gene family.
    
    CRITICAL PROMPT RULES:
    1. EXACT SYMBOL ONLY: Provide the short symbol (e.g., 'SPS', 'sh2').
    2. PREREQUISITE: Only use this tool AFTER discovering the symbol from literature or if the user explicitly provides it.
    """
    logger.debug(f"[Gene Tool] Organism: {organism} | Symbol: {gene_symbol}")
    
    # 1. Update fetcher to return a LIST of IDs (capped at 3 to avoid context overflow)
    async def _fetch_gene_ids(org: str, sym: str, session: aiohttp.ClientSession, limit: int = 3) -> list[str]:
        # Using [Gene] is strict, using [All Fields] is slightly looser for gene families
        entrez_query = f"{org}[Organism] AND {sym}[Gene]"
        search_url = f"{EUTILS_BASE}/esearch.fcgi"
        params = build_eutils_params(db="gene", term=entrez_query, retmode="json", retmax=limit)
        
        async with limiter:
            async with session.get(search_url, params=params) as resp:
                data = await resp.json()
        return data.get("esearchresult", {}).get("idlist", [])

    async with aiohttp.ClientSession() as session:
        try:
            # Fetch the batch of IDs
            gene_ids = await _fetch_gene_ids(organism, gene_symbol, session)
            
            # Fallback logic
            if not gene_ids and organism.lower() in ["saccharum", "saccharum officinarum", "sugarcane"]:
                logger.warning(f"No '{gene_symbol}' found in Saccharum. Falling back to Sorghum bicolor.")
                organism = "Sorghum bicolor"
                gene_ids = await _fetch_gene_ids(organism, gene_symbol, session)
                
            if not gene_ids:
                # If strict [Gene] search fails, try a slightly broader search before giving up
                fallback_query = f"{organism}[Organism] AND {gene_symbol}[All Fields]"
                search_url = f"{EUTILS_BASE}/esearch.fcgi"
                params = build_eutils_params(db="gene", term=fallback_query, retmode="json", retmax=3)
                async with limiter:
                    async with session.get(search_url, params=params) as resp:
                        data = await resp.json()
                gene_ids = data.get("esearchresult", {}).get("idlist", [])

                if not gene_ids:
                    return f"❌ No curated gene data found for '{gene_symbol}' in {organism}. It may be uncurated or go by a different official symbol."

            # 2. Batch fetch metadata using Datasets API
            ids_string = ",".join(gene_ids)
            ds_url = f"{DATASETS_BASE}/gene/id/{ids_string}/dataset_report"
            
            async with limiter:
                async with session.get(ds_url, headers=get_datasets_headers()) as resp:
                    if resp.status != 200:
                        raise ValueError(f"Datasets API failed: {await resp.text()}")
                    ds_data = await resp.json()
            
            reports = ds_data.get("reports", [])
            if not reports:
                return f"❌ Metadata not found for Gene IDs: {ids_string}."
            
            # 3. Format multiple gene reports
            formatted_results = []
            for report in reports:
                gene_data = report.get("gene", {})
                symbol = gene_data.get("symbol", "Unknown")
                desc = gene_data.get("description", "Unknown")
                current_gene_id = gene_data.get("gene_id", "Unknown")
                chromosomes = ", ".join(gene_data.get("chromosomes", []))
                summary = gene_data.get("summary", "No summary available.")
                
                go_data = gene_data.get("gene_ontology", {})
                functions = [f.get("name") for f in go_data.get("molecular_functions", [])]
                processes = [p.get("name") for p in go_data.get("biological_processes", [])]
                
                formatted_results.append(
                    f"✅ METADATA FOR: {symbol} (NCBI ID: {current_gene_id})\n"
                    f"- Organism: {organism}\n"
                    f"- Description: {desc}\n"
                    f"- Chromosome: {chromosomes if chromosomes else 'Unknown'}\n"
                    f"--- Gene Ontology ---\n"
                    f"- Molecular Functions: {', '.join(functions) if functions else 'None'}\n"
                    f"- Biological Processes: {', '.join(processes) if processes else 'None'}\n"
                    f"--- Summary ---\n{summary}\n"
                )

            return f"Found {len(formatted_results)} related gene(s):\n\n" + "\n====================\n".join(formatted_results)

        except Exception as e:
            logger.error(f"[Gene Tool] Error: {str(e)}")
            raise e
        
@tool(args_schema=GenomeSearchArgs)
async def search_ncbi_genome(organism_or_cultivar: str) -> str:
    """
    Search for genome assembly statistics (sequence length, chromosomes, GC percentage, gene counts).
    Use this for high-level species or cultivar genome information.
    """
    logger.debug(f"[Genome Tool] Target: {organism_or_cultivar}")
    
    async with aiohttp.ClientSession() as session:
        try:
            search_url = f"{EUTILS_BASE}/esearch.fcgi"
            params = build_eutils_params(db="assembly", term=organism_or_cultivar, retmode="json", retmax=1)
            
            async with limiter:
                async with session.get(search_url, params=params) as resp:
                    search_data = await resp.json()
            
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return f"❌ No genome assembly found for '{organism_or_cultivar}'."

            # Retrieve Accession
            assembly_id = id_list[0]
            summary_url = f"{EUTILS_BASE}/esummary.fcgi"
            summary_params = build_eutils_params(db="assembly", id=assembly_id, retmode="json")
            
            async with limiter:
                async with session.get(summary_url, params=summary_params) as resp:
                    summary_data = await resp.json()
            
            result = summary_data.get("result", {}).get(assembly_id, {})
            accession = result.get("assemblyaccession")
            
            if not accession:
                return "❌ Could not resolve a valid Accession ID."

            # Fetch Dataset Report
            ds_url = f"{DATASETS_BASE}/genome/accession/{accession}/dataset_report"
            async with limiter:
                async with session.get(ds_url, headers=get_datasets_headers()) as resp:
                    ds_data = await resp.json()
            
            reports = ds_data.get("reports", [])
            if not reports:
                return "❌ No dataset report found."
                
            return _format_dataset_report(reports[0])

        except Exception as e:
            logger.error(f"[Genome Tool] Error: {str(e)}")
            raise e

def _unwrap_secret(value: Any) -> str:
    """Safely extracts the string from a Pydantic SecretStr, or returns the string itself."""
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()
    return str(value)

def build_eutils_params(**kwargs) -> Dict[str, Any]:
    """Helper function to cleanly pass params via aiohttp instead of manual URL building."""
    params = kwargs.copy()
    
    if settings.ncbi_tool:
        # NCBI STRICT RULE: Tool name must NOT contain spaces
        raw_tool = _unwrap_secret(settings.ncbi_tool)
        params['tool'] = raw_tool.replace(" ", "_")
        
    if settings.ncbi_email:
        params['email'] = _unwrap_secret(settings.ncbi_email)
        
    if settings.ncbi_api_key:
        params['api_key'] = _unwrap_secret(settings.ncbi_api_key)
        
    return params

def get_datasets_headers() -> Dict[str, str]:
    """Helper to generate headers for Datasets v2 API, including optional API key."""
    headers = {"Accept": "application/json"}
    if settings.ncbi_api_key:
        headers["api-key"] = _unwrap_secret(settings.ncbi_api_key)
    return headers

def _format_dataset_report(report: Dict[str, Any]) -> str:
    """Formats the complex JSON report into a clean string for the LLM."""
    accession = report.get("accession", "Unknown")
    org = report.get("organism", {})
    asm = report.get("assembly_info", {})
    stats = report.get("assembly_stats", {})
    anno = report.get("annotation_info", {})
    
    # Extract Gene Counts if available
    gene_counts = anno.get("stats", {}).get("gene_counts", {})
    total_genes = gene_counts.get("total", "Data not available")
    protein_coding = gene_counts.get("protein_coding", "Data not available")
    
    return (
        f"✅ GENOME METADATA FOUND:\n"
        f"--- Basic Info ---\n"
        f"- Accession: {accession}\n"
        f"- Scientific Name: {org.get('sci_name', 'Unknown')} (TaxID: {org.get('tax_id', 'Unknown')})\n"
        f"- Cultivar/Strain: {org.get('infraspecific_names', {}).get('cultivar', org.get('strain', 'Unknown'))}\n"
        f"--- Assembly Details ---\n"
        f"- Assembly Name: {asm.get('assembly_name', 'Unknown')}\n"
        f"- Assembly Level: {asm.get('assembly_level', 'Unknown')}\n"
        f"- Release Date: {asm.get('release_date', 'Unknown')}\n"
        f"- Submitter: {asm.get('submitter', 'Unknown')}\n"
        f"--- Statistics ---\n"
        f"- Total Sequence Length: {stats.get('total_sequence_length', 'Unknown')} bp\n"
        f"- Total Chromosomes: {stats.get('total_number_of_chromosomes', 'Unknown')}\n"
        f"- GC Percentage: {stats.get('gc_percent', 'Unknown')}%\n"
        f"--- Annotation (Genes) ---\n"
        f"- Total Genes Annotated: {total_genes}\n"
        f"- Protein-Coding Genes: {protein_coding}\n"
    )
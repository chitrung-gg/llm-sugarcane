import aiohttp
import urllib.parse
from typing import Optional, Dict, Any
from loguru import logger
from langchain_core.tools import tool

# Base URLs
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DATASETS_BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2"

@tool
async def search_ncbi_genome(query: str) -> str:
    """
    The primary tool for searching genome metadata on NCBI.
    Accepts common names, scientific names, or cultivars (e.g., 'sugarcane r570', 'Saccharum').
    Uses a multi-step process: fuzzy search via E-utilities, Accession resolution, and 
    Datasets v2 metadata retrieval.
    """
    logger.debug(f"[NCBI Tool] Searching for genome metadata: {query}")
    safe_query = urllib.parse.quote(query.strip())
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Fuzzy search using E-utilities (esearch)
            # Entrez is much better at matching loose terms like "sugarcane r570".
            search_url = f"{EUTILS_BASE}/esearch.fcgi?db=assembly&term={safe_query}&retmode=json&retmax=1"
            async with session.get(search_url) as resp:
                if resp.status != 200:
                    return f"Error: NCBI E-search failed with status {resp.status}"
                search_data = await resp.json()
            
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            
            if not id_list:
                # FALLBACK: Try Datasets Taxonomy search if Entrez fails
                return await _fallback_taxon_search(session, query)

            # 2. Retrieve detailed summary to get the Accession (esummary)
            assembly_id = id_list[0]
            summary_url = f"{EUTILS_BASE}/esummary.fcgi?db=assembly&id={assembly_id}&retmode=json"
            async with session.get(summary_url) as resp:
                summary_data = await resp.json()
            
            # Extract the Accession ID (e.g., GCA_002018215.1)
            result = summary_data.get("result", {}).get(assembly_id, {})
            accession = result.get("assemblyaccession")
            
            if not accession:
                return "❌ Found a record ID but could not resolve a valid Accession."

            # 3. Fetch standard Dataset Report using the Accession
            # This provides the clean, nested metadata we need.
            ds_url = f"{DATASETS_BASE}/genome/accession/{accession}/dataset_report"
            async with session.get(ds_url, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    return f"❌ NCBI Datasets API failed to find report for {accession}."
                ds_data = await resp.json()
            
            reports = ds_data.get("reports", [])
            if reports:
                return _format_dataset_report(reports[0])
                
            return "❌ No dataset report found for the resolved accession."

        except Exception as e:
            logger.error(f"[NCBI Tool] System Error: {str(e)}")
            return f"System Error while calling NCBI: {str(e)}"

@tool
async def search_ncbi_genes(query: str, limit: int = 5) -> str:
    """
    Search for functional genes and their descriptions on NCBI.
    Use this when the user asks 'which gene regulates trait X' or 'find genes related to Y'.
    Example: 'sugarcane sugar content', 'sucrose metabolism sugarcane'.
    """
    logger.debug(f"[NCBI Gene Tool] Searching for genes: {query}")
    safe_query = urllib.parse.quote(query.strip())
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Search Gene DB (db=gene)
            search_url = f"{EUTILS_BASE}/esearch.fcgi?db=gene&term={safe_query}&retmode=json&retmax={limit}"
            async with session.get(search_url) as resp:
                search_data = await resp.json()
            
            gene_ids = search_data.get("esearchresult", {}).get("idlist", [])
            if not gene_ids:
                return f"❌ No genes found on NCBI matching the keywords: '{query}'"

            # 2. Fetch Gene Summaries
            summary_url = f"{EUTILS_BASE}/esummary.fcgi?db=gene&id={','.join(gene_ids)}&retmode=json"
            async with session.get(summary_url) as resp:
                summary_data = await resp.json()
            
            results = []
            for uid in gene_ids:
                gene_info = summary_data.get("result", {}).get(uid, {})
                name = gene_info.get("name", "Unknown")
                desc = gene_info.get("description", "No description available")
                org = gene_info.get("organism", {}).get("scientificname", "Unknown")
                results.append(f"🧬 Gene: {name} ({org})\n   Description: {desc}\n   NCBI ID: {uid}")

            return "✅ GENE SEARCH RESULTS:\n\n" + "\n\n".join(results)

        except Exception as e:
            return f"Error searching NCBI Genes: {str(e)}"

@tool
async def get_ncbi_gene_metadata(gene_id: str) -> str:
    """
    Retrieve deep, specific metadata for a single Gene using the NCBI Datasets v2 API.
    Use this AFTER you have discovered a Gene ID using 'search_ncbi_genes'.
    Accepts a single numeric NCBI Gene ID (e.g., '19171').
    """
    logger.debug(f"[NCBI Tool] Fetching deep metadata for Gene ID: {gene_id}")

    async with aiohttp.ClientSession() as session:
        try:
            ds_url = f"{DATASETS_BASE}/gene/id/{gene_id}/dataset_report"
            async with session.get(ds_url, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    return f"❌ NCBI Datasets API failed to find metadata for Gene ID {gene_id}."
                ds_data = await resp.json()
                
            reports = ds_data.get("reports", [])
            if not reports:
                return f"❌ No detailed metadata found for Gene ID {gene_id}."
                
            gene_data = reports[0].get("gene", {})
            symbol = gene_data.get("symbol", "Unknown")
            description = gene_data.get("description", "Unknown")
            taxname = gene_data.get("taxname", "Unknown")
            synonyms = ", ".join(gene_data.get("synonyms", []))
            summary = gene_data.get("summary", "No summary available.")
            
            return (
                f"✅ DETAILED GENE METADATA:\n"
                f"- Symbol: {symbol}\n"
                f"- Organism: {taxname}\n"
                f"- Description: {description}\n"
                f"- Synonyms: {synonyms if synonyms else 'None'}\n"
                f"- Summary: {summary}"
            )

        except Exception as e:
            return f"Error fetching gene metadata: {str(e)}"

async def _fallback_taxon_search(session: aiohttp.ClientSession, query: str) -> str:
    """
    Fallback mechanism: If E-utilities fails to find an Assembly, this function 
    searches the Taxonomy API by name, extracts the TaxID, and fetches the genome.
    """
    safe_query = urllib.parse.quote(query.strip())
    tax_url = f"{DATASETS_BASE}/taxonomy/name/{safe_query}"

    try:
        async with session.get(tax_url, headers={"Accept": "application/json"}) as resp:
            if resp.status != 200:
                return "❌ No specific assembly found. Try searching by scientific name instead."
            tax_data = await resp.json()
        
        # Extract Taxonomy ID
        taxons = tax_data.get("sci_name_and_ids", [])
        if not taxons:
            return f"❌ Taxonomy found, but no valid TaxID for '{query}'"
            
        tax_id = taxons[0].get("tax_id")
        
        # Use TaxID to fetch the Genome Dataset Report
        genome_url = f"{DATASETS_BASE}/genome/taxon/{tax_id}/dataset_report"
        async with session.get(genome_url, headers={"Accept": "application/json"}) as resp:
            if resp.status != 200:
                return f"❌ Taxonomy resolved to TaxID {tax_id}, but no genome dataset exists."
            genome_data = await resp.json()
            
        reports = genome_data.get("reports", [])
        if reports:
            logger.debug(f"[NCBI Tool] Fallback successful using TaxID: {tax_id}")
            return _format_dataset_report(reports[0])
            
        return f"❌ No genome reports found for TaxID {tax_id}."
        
    except Exception as e:
        return f"System Error during fallback search: {str(e)}"

def _format_dataset_report(report: Dict[str, Any]) -> str:
    """Formats the complex JSON report into a clean string for the LLM."""
    accession = report.get("accession", "Unknown")
    org = report.get("organism", {})
    asm = report.get("assembly_info", {})
    check = report.get("assembly_stats", {})
    
    return (
        f"✅ GENOME METADATA FOUND:\n"
        f"- Accession: {accession}\n"
        f"- Scientific Name: {org.get('sci_name', 'Unknown')}\n"
        f"- Common Name: {org.get('common_name', 'N/A')}\n"
        f"- Cultivar: {org.get('infraspecific_names', {}).get('cultivar', 'Unknown')}\n"
        f"- Assembly Name: {asm.get('assembly_name', 'Unknown')}\n"
        f"- Assembly Level: {asm.get('assembly_level', 'Unknown')}\n"
        f"- Total Sequence Length: {check.get('total_sequence_length', 'Unknown')} bp\n"
        f"- Submitter: {asm.get('submitter', 'Unknown')}\n"
        f"- Release Date: {asm.get('release_date', 'Unknown')}"
    )
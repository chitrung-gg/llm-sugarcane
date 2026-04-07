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
    
    CRITICAL PROMPT RULES:
    1. The query MUST be concise keywords. 
    2. DO NOT use long sentences or complex hybrid taxonomic names (e.g., NEVER use 'Saccharum officinarum X spontaneum var R570').
    3. Use simple combinations of common name + cultivar (e.g., 'sugarcane r570') or base scientific name (e.g., 'Saccharum officinarum').
    """
    logger.debug(f"[NCBI Tool] Searching for genome metadata: {query}")
    safe_query = urllib.parse.quote(query.strip())
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Fuzzy search using E-utilities (esearch)
            search_url = f"{EUTILS_BASE}/esearch.fcgi?db=assembly&term={safe_query}&retmode=json&retmax=1"
            async with session.get(search_url) as resp:
                if resp.status != 200:
                    raise ValueError(f"NCBI E-search failed with status {resp.status}")
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
            
            result = summary_data.get("result", {}).get(assembly_id, {})
            accession = result.get("assemblyaccession")
            
            if not accession:
                raise ValueError(f"Found NCBI record ID {assembly_id} but could not resolve a valid Accession.")

            # 3. Fetch standard Dataset Report using the Accession
            ds_url = f"{DATASETS_BASE}/genome/accession/{accession}/dataset_report"
            async with session.get(ds_url, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    raise ValueError(f"NCBI Datasets API failed to find report for {accession}.")
                ds_data = await resp.json()
            
            reports = ds_data.get("reports", [])
            if not reports:
                raise ValueError(f"No dataset report found for the resolved accession {accession}.")
                
            return _format_dataset_report(reports[0])

        except Exception as e:
            logger.error(f"[NCBI Tool] System Error: {str(e)}")
            raise e

@tool
async def search_ncbi_genes(query: str, limit: int = 5) -> str:
    """
    Search for functional genes and their descriptions on NCBI.
    Use this when the user asks 'which gene regulates trait X' or 'find genes related to Y'.
    
    CRITICAL PROMPT RULES:
    1. The query MUST be a concise, short keyword or phrase (e.g., 'r570', 'sucrose metabolism', 'ScDir').
    2. DO NOT pass long biological names, full hybrid names, or conversational sentences.
    """
    logger.debug(f"[NCBI Gene Tool] Searching for genes: {query}")
    safe_query = urllib.parse.quote(query.strip())
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Search Gene DB (db=gene)
            search_url = f"{EUTILS_BASE}/esearch.fcgi?db=gene&term={safe_query}&retmode=json&retmax={limit}"
            async with session.get(search_url) as resp:
                if resp.status != 200:
                    raise ValueError(f"NCBI E-search failed with status {resp.status}")
                search_data = await resp.json()
            
            gene_ids = search_data.get("esearchresult", {}).get("idlist", [])
            if not gene_ids:
                raise ValueError(f"No genes found on NCBI matching the keywords: '{query}'")

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
            logger.error(f"Error searching NCBI Genes: {str(e)}")
            raise e

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
                    raise ValueError(f"NCBI Datasets API failed to find metadata for Gene ID {gene_id}.")
                ds_data = await resp.json()
                
            reports = ds_data.get("reports", [])
            if not reports:
                raise ValueError(f"No detailed metadata found on NCBI for Gene ID {gene_id}.")
                
            gene_data = reports[0].get("gene", {})
            symbol = gene_data.get("symbol", "Unknown")
            description = gene_data.get("description", "Unknown")
            taxname = gene_data.get("taxname", "Unknown")
            chromosomes = ", ".join(gene_data.get("chromosomes", []))
            synonyms = ", ".join(gene_data.get("synonyms", []))
            summary = gene_data.get("summary", "No summary available.")
            
            # Extract GO Terms (Gene Ontology)
            go_data = gene_data.get("gene_ontology", {})
            functions = [f.get("name") for f in go_data.get("molecular_functions", [])]
            processes = [p.get("name") for p in go_data.get("biological_processes", [])]
            
            return (
                f"✅ DETAILED GENE METADATA:\n"
                f"- Symbol: {symbol} (ID: {gene_id})\n"
                f"- Organism: {taxname}\n"
                f"- Description: {description}\n"
                f"- Chromosome Location: {chromosomes if chromosomes else 'Unknown'}\n"
                f"- Synonyms: {synonyms if synonyms else 'None'}\n"
                f"--- Gene Ontology ---\n"
                f"- Molecular Functions: {', '.join(functions) if functions else 'Unknown'}\n"
                f"- Biological Processes: {', '.join(processes) if processes else 'Unknown'}\n"
                f"--- Summary ---\n"
                f"{summary}"
            )

        except Exception as e:
            logger.error(f"Error fetching gene metadata: {str(e)}")
            raise e

async def _fallback_taxon_search(session: aiohttp.ClientSession, query: str) -> str:
    """
    Fallback mechanism: If E-utilities fails, we do a broad search using the taxon endpoint.
    NCBI's {taxons} parameter accepts both numeric IDs and string names directly!
    """
    # E.g., turns "sugarcane" into "sugarcane" or "sugarcane r570" into "sugarcane%20r570"
    safe_query = urllib.parse.quote(query.strip())
    
    # We use your exact allowed endpoint: /genome/taxon/{taxons}/dataset_report
    genome_url = f"{DATASETS_BASE}/genome/taxon/{safe_query}/dataset_report"
    
    try:
        async with session.get(genome_url, headers={"Accept": "application/json"}) as resp:
            if resp.status != 200:
                raise ValueError(f"No genome dataset found for taxon '{query}'.")
            genome_data = await resp.json()
            
        reports = genome_data.get("reports", [])
        if reports:
            logger.debug(f"[NCBI Tool] Fallback successful using broad taxon search for: {query}")
            return _format_dataset_report(reports[0])
            
        raise ValueError(f"No genome reports found for taxon '{query}'.")
        
    except Exception as e:
        logger.error(f"System Error during fallback search: {str(e)}")
        raise e

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
# import re

# import aiohttp
# from typing import Optional, Dict, Any, cast
# from aiolimiter import AsyncLimiter
# from loguru import logger
# from langchain_core.tools import tool

# from app.configs.settings.settings import get_settings

# settings = get_settings()
# # Base URLs
# EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
# DATASETS_BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2"

# # Set up the rate limiter
# RATE_LIMIT = 10 if settings.ncbi_api_key else 3
# limiter = AsyncLimiter(RATE_LIMIT, 1)

# def _unwrap_secret(value: Any) -> str:
#     """Safely extracts the string from a Pydantic SecretStr, or returns the string itself."""
#     if hasattr(value, "get_secret_value"):
#         return value.get_secret_value()
#     return str(value)

# def build_eutils_params(**kwargs) -> Dict[str, Any]:
#     """Helper function to cleanly pass params via aiohttp instead of manual URL building."""
#     params = kwargs.copy()
    
#     if settings.ncbi_tool:
#         # NCBI STRICT RULE: Tool name must NOT contain spaces
#         raw_tool = _unwrap_secret(settings.ncbi_tool)
#         params['tool'] = raw_tool.replace(" ", "_")
        
#     if settings.ncbi_email:
#         params['email'] = _unwrap_secret(settings.ncbi_email)
        
#     if settings.ncbi_api_key:
#         params['api_key'] = _unwrap_secret(settings.ncbi_api_key)
        
#     return params

# def get_datasets_headers() -> Dict[str, str]:
#     """Helper to generate headers for Datasets v2 API, including optional API key."""
#     headers = {"Accept": "application/json"}
#     if settings.ncbi_api_key:
#         headers["api-key"] = _unwrap_secret(settings.ncbi_api_key)
#     return headers

# @tool
# async def search_ncbi_genome(query: str) -> str:
#     """
#     Search for genome assembly metadata on NCBI (e.g., sequence length, chromosomes, GC percentage, gene counts).
#     Use this tool when the user asks for general information about a species' genome or a specific cultivar's assembly.
    
#     CRITICAL PROMPT RULES:
#     1. CONCISE KEYWORDS ONLY: The query must be short and focused (e.g., 'sugarcane', 'sugarcane r570', 'Saccharum').
#     2. NO CONVERSATION: Never pass full sentences or questions (e.g., BAD: "what is the genome of sugarcane r570").
#     3. AVOID COMPLEX HYBRIDS: Do not use long taxonomic crosses. Stick to the base scientific name or common name + cultivar.
#     """
#     logger.debug(f"[NCBI Tool] Searching for genome metadata: {query}")
#     clean_query = query.strip()

#     # Sanitize common conversational mistakes from the LLM
#     clean_query = query.lower()
#     for filler in ["what is ", "genome of ", "metadata for ", "?", "the "]:
#         clean_query = clean_query.replace(filler, "")
#     clean_query = clean_query.strip()
    
#     async with aiohttp.ClientSession() as session:
#         try:
#             # 1. Fuzzy search using E-utilities (esearch)
#             search_url = f"{EUTILS_BASE}/esearch.fcgi"
#             params = build_eutils_params(db="assembly", term=clean_query, retmode="json", retmax=1)
            
#             async with limiter:
#                 async with session.get(search_url, params=params) as resp:
#                     if resp.status != 200:
#                         # LOG THE ACTUAL ERROR FROM NCBI TO DEBUG
#                         error_text = await resp.text()
#                         raise ValueError(f"NCBI E-search failed with status {resp.status}. Details: {error_text}")
#                     search_data = await resp.json()
            
#             id_list = search_data.get("esearchresult", {}).get("idlist", [])
            
#             if not id_list:
#                 return await _fallback_taxon_search(session, query)

#             # 2. Retrieve detailed summary to get the Accession (esummary)
#             assembly_id = id_list[0]
#             summary_url = f"{EUTILS_BASE}/esummary.fcgi"
#             summary_params = build_eutils_params(db="assembly", id=assembly_id, retmode="json")
            
#             async with limiter:
#                 async with session.get(summary_url, params=summary_params) as resp:
#                     if resp.status != 200:
#                         error_text = await resp.text()
#                         raise ValueError(f"NCBI E-summary failed with status {resp.status}. Details: {error_text}")
#                     summary_data = await resp.json()
            
#             result = summary_data.get("result", {}).get(assembly_id, {})
#             accession = result.get("assemblyaccession")
            
#             if not accession:
#                 raise ValueError(f"Found NCBI record ID {assembly_id} but could not resolve a valid Accession.")

#             # 3. Fetch standard Dataset Report using the Accession
#             ds_url = f"{DATASETS_BASE}/genome/accession/{accession}/dataset_report"
            
#             async with limiter:
#                 async with session.get(ds_url, headers=get_datasets_headers()) as resp:
#                     if resp.status != 200:
#                         raise ValueError(f"NCBI Datasets API failed to find report for {accession}.")
#                     ds_data = await resp.json()
            
#             reports = ds_data.get("reports", [])
#             if not reports:
#                 raise ValueError(f"No dataset report found for the resolved accession {accession}.")
                
#             return _format_dataset_report(reports[0])

#         except Exception as e:
#             logger.error(f"[NCBI Tool] System Error: {str(e)}")
#             raise e


# @tool
# async def search_ncbi_genes(query: str, limit: int = 5) -> str:
#     """
#     Search for functional genes and their descriptions on NCBI.
    
#     CRITICAL PROMPT RULES:
#     1. FORMAT: Output ONLY the Organism Name followed by the Gene Symbol (e.g., 'Saccharum SPS').
#     2. STRIP WORDS: NEVER include the words 'gene', 'protein', or trait descriptions.
#     3. THE ORTHOLOG STRATEGY (CRITICAL): Sugarcane (Saccharum) is poorly annotated in NCBI. If your search for a Saccharum gene returns 0 results, you MUST call this tool again using a closely related model grass, such as 'Sorghum bicolor' or 'Zea mays' (e.g., search 'Sorghum bicolor SPS' instead).
#     """
#     logger.debug(f"[NCBI Gene Tool] Raw query received: {query}")
#     clean_query = query.strip()
    
#     gene = ""
#     # AUTO-FORMATTER: Transform "Saccharum SPS" into "Saccharum[Orgn] AND SPS[Gene]"
#     if " " in clean_query and "[" not in clean_query:
#         # Split into Organism (first word or two) and Gene (the rest)
#         parts = clean_query.split(" ")
#         if len(parts) >= 2:
#             # Handle binomial names like "Sorghum bicolor" vs single like "Saccharum"
#             if len(parts) >= 3 and parts[0][0].isupper() and parts[1].islower():
#                 orgn = f"{parts[0]} {parts[1]}"
#                 gene = " ".join(parts[2:])
#             else:
#                 orgn = parts[0]
#                 gene = " ".join(parts[1:])
                
#             ncbi_term = f"{orgn}[Orgn] AND {gene}[Gene]"
#         else:
#             ncbi_term = clean_query
#     else:
#         ncbi_term = clean_query

#     logger.debug(f"[NCBI Gene Tool] Formatted query for E-utilities: {ncbi_term}")
    
#     async with aiohttp.ClientSession() as session:
#         try:
#             # 1. Search Gene DB (db=gene)
#             search_url = f"{EUTILS_BASE}/esearch.fcgi"
#             params = build_eutils_params(db="gene", term=ncbi_term, retmode="json", retmax=limit)
            
#             async with limiter:
#                 async with session.get(search_url, params=params) as resp:
#                     if resp.status != 200:
#                         error_text = await resp.text()
#                         raise ValueError(f"NCBI E-search failed with status {resp.status}. Details: {error_text}")
#                     search_data = await resp.json()
            
#             gene_ids = search_data.get("esearchresult", {}).get("idlist", [])
#             if not gene_ids:
#                 return (
#                     f"❌ No genes found in the curated database for: '{ncbi_term}'.\n"
#                     f"SUGGESTION: Sugarcane genes are often uncurated. Try searching for this gene in a related species by calling this tool again with: 'Sorghum bicolor {gene}' or 'Zea mays {gene}'."
#                 )

#             # 2. Fetch Gene Summaries
#             summary_url = f"{EUTILS_BASE}/esummary.fcgi"
#             summary_params = build_eutils_params(db="gene", id=",".join(gene_ids), retmode="json")
            
#             async with limiter:
#                 async with session.get(summary_url, params=summary_params) as resp:
#                     if resp.status != 200:
#                         error_text = await resp.text()
#                         raise ValueError(f"NCBI E-summary failed with status {resp.status}. Details: {error_text}")
#                     summary_data = await resp.json()
            
#             results = []
#             for uid in gene_ids:
#                 gene_info = summary_data.get("result", {}).get(uid, {})
#                 name = gene_info.get("name", "Unknown")
#                 desc = gene_info.get("description", "No description available")
#                 org = gene_info.get("organism", {}).get("scientificname", "Unknown")
#                 results.append(f"🧬 Gene: {name} ({org})\n   Description: {desc}\n   NCBI ID: {uid}")

#             return "✅ GENE SEARCH RESULTS:\n\n" + "\n\n".join(results)

#         except Exception as e:
#             logger.error(f"Error searching NCBI Genes: {str(e)}")
#             raise e

# @tool
# async def get_ncbi_gene_metadata(gene_id: str) -> str:
#     """
#     Retrieve deep, specific metadata for a single Gene using the NCBI Datasets v2 API.
#     Use this tool to find gene ontology (GO terms), chromosome location, synonyms, and functional summaries.
    
#     CRITICAL PROMPT RULES:
#     1. EXACT ID REQUIRED: You MUST pass a single numeric NCBI Gene ID as a string (e.g., '19171', '10582').
#     2. DO NOT PASS NAMES: Never pass gene symbols, text, or query strings (e.g., BAD: 'SuSy', 'Saccharum SPS').
#     3. EXECUTION ORDER: You must successfully run the 'search_ncbi_genes' tool FIRST to discover the correct numeric Gene ID before calling this tool.
#     """
#     # 1. Intercept bad input immediately
#     clean_id = gene_id.strip()
#     if not clean_id.isdigit():
#         return "❌ ERROR: You must provide a valid NUMERIC Gene ID (e.g., '10582'). Do not pass gene names or symbols."
    
#     logger.debug(f"[NCBI Tool] Fetching deep metadata for Gene ID: {gene_id}")

#     async with aiohttp.ClientSession() as session:
#         try:
#             ds_url = f"{DATASETS_BASE}/gene/id/{gene_id}/dataset_report"
            
#             async with limiter:
#                 async with session.get(ds_url, headers=get_datasets_headers()) as resp:
#                     if resp.status != 200:
#                         raise ValueError(f"NCBI Datasets API failed to find metadata for Gene ID {gene_id}.")
#                     ds_data = await resp.json()
                
#             reports = ds_data.get("reports", [])
#             if not reports:
#                 raise ValueError(f"No detailed metadata found on NCBI for Gene ID {gene_id}.")
                
#             gene_data = reports[0].get("gene", {})
#             symbol = gene_data.get("symbol", "Unknown")
#             description = gene_data.get("description", "Unknown")
#             taxname = gene_data.get("taxname", "Unknown")
#             chromosomes = ", ".join(gene_data.get("chromosomes", []))
#             synonyms = ", ".join(gene_data.get("synonyms", []))
#             summary = gene_data.get("summary", "No summary available.")
            
#             # Extract GO Terms (Gene Ontology)
#             go_data = gene_data.get("gene_ontology", {})
#             functions = [f.get("name") for f in go_data.get("molecular_functions", [])]
#             processes = [p.get("name") for p in go_data.get("biological_processes", [])]
            
#             return (
#                 f"✅ DETAILED GENE METADATA:\n"
#                 f"- Symbol: {symbol} (ID: {gene_id})\n"
#                 f"- Organism: {taxname}\n"
#                 f"- Description: {description}\n"
#                 f"- Chromosome Location: {chromosomes if chromosomes else 'Unknown'}\n"
#                 f"- Synonyms: {synonyms if synonyms else 'None'}\n"
#                 f"--- Gene Ontology ---\n"
#                 f"- Molecular Functions: {', '.join(functions) if functions else 'Unknown'}\n"
#                 f"- Biological Processes: {', '.join(processes) if processes else 'Unknown'}\n"
#                 f"--- Summary ---\n"
#                 f"{summary}"
#             )

#         except Exception as e:
#             logger.error(f"Error fetching gene metadata: {str(e)}")
#             raise e


# async def _fallback_taxon_search(session: aiohttp.ClientSession, query: str) -> str:
#     """Fallback mechanism for Datasets v2 API."""
#     import urllib.parse
#     safe_query = urllib.parse.quote(query.strip())
#     genome_url = f"{DATASETS_BASE}/genome/taxon/{safe_query}/dataset_report"
    
#     try:
#         async with limiter:
#             async with session.get(genome_url, headers=get_datasets_headers()) as resp:
#                 if resp.status != 200:
#                     raise ValueError(f"No genome dataset found for taxon '{query}'.")
#                 genome_data = await resp.json()
            
#         reports = genome_data.get("reports", [])
#         if reports:
#             logger.debug(f"[NCBI Tool] Fallback successful using broad taxon search for: {query}")
#             return _format_dataset_report(reports[0])
            
#         raise ValueError(f"No genome reports found for taxon '{query}'.")
        
#     except Exception as e:
#         logger.error(f"System Error during fallback search: {str(e)}")
#         raise e


# def _format_dataset_report(report: Dict[str, Any]) -> str:
#     """Formats the complex JSON report into a clean string for the LLM."""
#     accession = report.get("accession", "Unknown")
#     org = report.get("organism", {})
#     asm = report.get("assembly_info", {})
#     stats = report.get("assembly_stats", {})
#     anno = report.get("annotation_info", {})
    
#     # Extract Gene Counts if available
#     gene_counts = anno.get("stats", {}).get("gene_counts", {})
#     total_genes = gene_counts.get("total", "Data not available")
#     protein_coding = gene_counts.get("protein_coding", "Data not available")
    
#     return (
#         f"✅ GENOME METADATA FOUND:\n"
#         f"--- Basic Info ---\n"
#         f"- Accession: {accession}\n"
#         f"- Scientific Name: {org.get('sci_name', 'Unknown')} (TaxID: {org.get('tax_id', 'Unknown')})\n"
#         f"- Cultivar/Strain: {org.get('infraspecific_names', {}).get('cultivar', org.get('strain', 'Unknown'))}\n"
#         f"--- Assembly Details ---\n"
#         f"- Assembly Name: {asm.get('assembly_name', 'Unknown')}\n"
#         f"- Assembly Level: {asm.get('assembly_level', 'Unknown')}\n"
#         f"- Release Date: {asm.get('release_date', 'Unknown')}\n"
#         f"- Submitter: {asm.get('submitter', 'Unknown')}\n"
#         f"--- Statistics ---\n"
#         f"- Total Sequence Length: {stats.get('total_sequence_length', 'Unknown')} bp\n"
#         f"- Total Chromosomes: {stats.get('total_number_of_chromosomes', 'Unknown')}\n"
#         f"- GC Percentage: {stats.get('gc_percent', 'Unknown')}%\n"
#         f"--- Annotation (Genes) ---\n"
#         f"- Total Genes Annotated: {total_genes}\n"
#         f"- Protein-Coding Genes: {protein_coding}\n"
#     )
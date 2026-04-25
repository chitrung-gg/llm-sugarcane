import asyncio
from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_neo4j import Neo4jGraph
from langchain_qdrant import QdrantVectorStore
from loguru import logger

from app.core.tools.registry.registry_tool import register_agent_tool

def make_graph_rag_tool(
    vector_store_solid: QdrantVectorStore,
    vector_store_volatile: QdrantVectorStore,
    knowledge_graph: Neo4jGraph
):
    @register_agent_tool
    @tool("search_knowledge_graph")
    async def search_knowledge_graph(query: str, top_k: int = 5) -> str:
        """
        Searches the internal knowledge graph for biological entities and relationships.
        Use this tool to find multi-hop connections between genes, diseases, traits, and papers.
        """
        logger.info(f"Searching Knowledge Graph for: {query}")
        
        try:
            # 1. Concurrent Semantic Search on BOTH Qdrant collections
            solid_task = vector_store_solid.asimilarity_search_with_score(query, k=top_k)
            volatile_task = vector_store_volatile.asimilarity_search_with_score(query, k=top_k)
            
            solid_results, volatile_results = await asyncio.gather(solid_task, volatile_task)

            # Combine, tag, and sort by Hybrid score (No hardcoded thresholds!)
            combined_results = []
            for doc, score in solid_results:
                combined_results.append((doc, score, "SOLID"))
            for doc, score in volatile_results:
                combined_results.append((doc, score, "VOLATILE"))
                
            # Sort descending by score and slice the top_k absolute best matches
            combined_results.sort(key=lambda x: x[1], reverse=True)
            top_results = combined_results[:top_k]

            # Extract unique global_ids, prioritizing the solid database
            entity_ids = set()
            fallback_docs = []

            for doc, score, tier in top_results:
                if "global_id" in doc.metadata:
                    entity_ids.add(doc.metadata["global_id"])
                fallback_docs.append(f"[{tier} | Score: {score:.2f}] {doc.page_content}")
                logger.debug(f"[GraphRAG] Kept entity from {tier} with score {score:.2f}")

            if not entity_ids:
                return "Found no relevant starting entities in the vector stores to query the Knowledge Graph."

            # 2. Graph Retrieval from Neo4j (With Trust Filtering)
            # COALESCE(property, default_value) returns the property if it exists, otherwise the default.
            # We assume legacy data (pre-update) was curated/safe, so we default confidence to 1.0.
            # We filter out edges with < 0.4 confidence to protect the LLM from hallucinations
            cypher_query = """
                MATCH (e)-[r1]-(n1)
                WHERE e.global_id IN $entity_ids
                  AND COALESCE(r1.confidence, 1.0) >= 0.4
                  
                OPTIONAL MATCH (n1)-[r2]-(n2)
                WHERE COALESCE(r2.confidence, 1.0) >= 0.4
                
                RETURN e.name AS e_name, 
                       type(r1) AS r1_type, 
                       COALESCE(r1.confidence, 1.0) AS r1_conf, 
                       COALESCE(r1.source_tier, 'curated') AS r1_tier,
                       n1.name AS n1_name, 
                       type(r2) AS r2_type, 
                       COALESCE(r2.confidence, 1.0) AS r2_conf, 
                       COALESCE(r2.source_tier, 'curated') AS r2_tier,
                       n2.name AS n2_name
                LIMIT 50
            """

            # Execute query using the collected UUIDs
            records = knowledge_graph.query(cypher_query, params={"entity_ids": list(entity_ids)})
                
            subgraph = []
            for record in records:
                # Parse Node 1 to Node 2
                e_name = record.get("e_name", "Unknown")
                rel1_type = record.get("r1_type", "RELATED_TO")
                n1_name = record.get("n1_name", "Unknown")
                
                # Format the edge with its provenance tags so the LLM knows how much to trust it!
                r1_conf = record.get("r1_conf") or 1.0
                r1_tier = record.get("r1_tier") or "curated"
                subgraph.append(f"({e_name}) -[{rel1_type} | Conf:{r1_conf} | Tier:{r1_tier}]-> ({n1_name})")
                
                # Parse Node 2 to Node 3 (if it exists)
                if record.get("r2_type") and record.get("n2_name"):
                    rel2_type = record.get("r2_type")
                    n2_name = record.get("n2_name", "Unknown")
                    r2_conf = record.get("r2_conf") or 1.0
                    r2_tier = record.get("r2_tier") or "curated"
                    subgraph.append(f"({n1_name}) -[{rel2_type} | Conf:{r2_conf} | Tier:{r2_tier}]-> ({n2_name})")

            # 3. Format result
            if not subgraph:
                # If Neo4j has no edges, fall back to returning the raw Qdrant chunks
                logger.debug("[GraphRAG Tool] Found entities but no edges. Falling back to vector chunks.")
                return "Found entities but no graph relationships. Raw context:\n" + "\n---\n".join(fallback_docs[:top_k])
                
            # Deduplicate
            unique_edges = list(set(subgraph))
            formatted_context = "Knowledge Graph Context:\n" + "\n".join(unique_edges)
            return formatted_context

        except Exception as e:
            logger.error(f"GraphRAG Tool failed: {str(e)}")
            return f"Error retrieving knowledge graph context: {str(e)}"
    
    return search_knowledge_graph
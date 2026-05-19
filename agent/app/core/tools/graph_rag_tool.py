import asyncio
import re
from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_neo4j import Neo4jGraph
from langchain_qdrant import QdrantVectorStore
from loguru import logger
from qdrant_client.http import models

from app.core.prompts.knowledge_graph_prompts import GRAPH_PRUNING_PROMPT
from app.schemas.agent.knowledge_graph import GraphPruningResult
from app.services.llm.llm_service import LLMService
from app.schemas.tool.knowledge_graph_schema import KnowledgeGraphInput
from app.configs.settings.settings import get_settings
from app.core.tools.registry.registry_tool import register_agent_tool

def make_graph_rag_tool(
    vector_store_solid: QdrantVectorStore,
    vector_store_volatile: QdrantVectorStore,
    knowledge_graph: Neo4jGraph,
    llm_service: LLMService
):
    @register_agent_tool
    @tool(args_schema=KnowledgeGraphInput)
    # Add owner_id to the function signature!
    async def search_knowledge_graph(query: str, top_k: int = 5) -> str:
        """
        Searches the internal knowledge graph for biological entities and relationships.
        Use this tool to find multi-hop connections between genes, diseases, traits, and papers.
        """
        logger.info(f"Searching Knowledge Graph for: {query}")
        
        settings = get_settings()
        try:
            # 1. Concurrent Semantic Search on BOTH Qdrant collections
            
            solid_task = vector_store_solid.asimilarity_search_with_score(
                query, 
                k=top_k
            )
            volatile_task = vector_store_volatile.asimilarity_search_with_score(
                query, 
                k=top_k
            )
            
            solid_results, volatile_results = await asyncio.gather(solid_task, volatile_task)

            # Combine, tag, and sort by Hybrid score
            combined_results = []
            for doc, score in solid_results:
                combined_results.append((doc, score, "SOLID"))
            for doc, score in volatile_results:
                combined_results.append((doc, score, "VOLATILE"))
                
            combined_results.sort(key=lambda x: x[1], reverse=True)
            top_results = combined_results[:top_k]

            # Extract the Natural Keys instead of global_id
            entity_ids = set()
            file_ids = set()

            for doc, score, tier in top_results:
                if score < settings.KNOWLEDGE_GRAPH_SCORE_THRESHOLD:
                    logger.debug(f"[GraphRAG] Dropping chunk {tier} due to low score: {score:.2f}")
                    continue
                
                # Collect the specific files Qdrant found
                if "file_id" in doc.metadata:
                    file_ids.add(doc.metadata["file_id"])

                # Unpack the "Label::Name" array we created during ingestion
                e_ids = doc.metadata.get("entity_ids", [])
                for eid in e_ids:
                    entity_ids.add(eid)

            if not entity_ids or not file_ids:
                return ""

            # 2. Graph Retrieval from Neo4j (Dynamically filtering by Natural Keys & File ID)
            cypher_query = """
                MATCH (e)
                WHERE e.id IN $entity_ids
                  
                // Traverse 1 to 2 hops
                MATCH p = (e)-[r*1..2]-(connected)
                
                // Strict Scoping: Only grab Edges in allowed files
                WHERE ALL(rel IN relationships(p) WHERE rel.source_file_id IN $file_ids)
                  AND ALL(rel IN relationships(p) WHERE COALESCE(rel.confidence, 1.0) >= 0.7)
                  
                RETURN [n IN nodes(p) | n.name] AS nodes, 
                       [rel IN relationships(p) | type(rel)] AS rels,
                       [rel IN relationships(p) | COALESCE(rel.confidence, 1.0)] AS confs
                LIMIT 15
            """

            # Execute query using the Natural Keys
            records = knowledge_graph.query(
                cypher_query, 
                params={
                    "entity_ids": list(entity_ids),
                    "file_ids": list(file_ids)
                }
            )
                
            subgraph = []
            for record in records:
                nodes = record["nodes"]
                rels = record["rels"]
                confs = record["confs"]
                
                # Reconstruct string: (A) -[CAUSES | Conf:0.9]-> (B)
                path_str = f"({nodes[0]})"
                for i, rel in enumerate(rels):
                    path_str += f" -[{rel} | Conf:{confs[i]}]-> ({nodes[i+1]})"
                subgraph.append(path_str)

            # 3. Format result
            if not subgraph:
                logger.debug("[GraphRAG Tool] Found entities but no edges inside target files. Returning empty.")
                return ""
                
            unique_edges = list(set(subgraph))

            if len(unique_edges) > 3:
                logger.debug(f"[GraphRAG] Pruning {len(unique_edges)} raw graph paths via LLM...")
                
                raw_paths_str = "\n".join(unique_edges)
                
                pruner_llm = llm_service.get_structured_tertiary_model(GraphPruningResult)
                
                prune_messages = GRAPH_PRUNING_PROMPT.format(
                    user_query=query,
                    raw_paths=raw_paths_str
                )
                
                try:
                    pruned_result: GraphPruningResult = await pruner_llm.ainvoke(prune_messages)
                    unique_edges = pruned_result.relevant_paths
                    logger.debug(f"[GraphRAG] Pruned down to {len(unique_edges)} highly relevant paths.")
                except Exception as e:
                    logger.warning(f"[GraphRAG] Pruning LLM failed, using raw edges. Error: {e}")

            # 3. Format result
            if not unique_edges:
                logger.debug("[GraphRAG] All edges were pruned as irrelevant. Falling back to vector chunks.")
                return ""
                
            formatted_context = "Knowledge Graph Context:\n" + "\n".join(unique_edges)
            return formatted_context

        except Exception as e:
            logger.error(f"GraphRAG Tool failed: {str(e)}")
            return f"Error retrieving knowledge graph context: {str(e)}"
    
    return search_knowledge_graph
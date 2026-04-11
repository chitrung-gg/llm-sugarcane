from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_neo4j import Neo4jGraph
from langchain_qdrant import QdrantVectorStore
from loguru import logger

from app.configs.storage.databases import neo4j_driver


def make_graph_rag_tool(
    vector_store: QdrantVectorStore,
    knowledge_graph: Neo4jGraph
):
    @tool("search_knowledge_graph")
    async def search_knowledge_graph(query: str, top_k: int = 5) -> str:
        """
        Searches the internal knowledge graph for biological entities and relationships.
        Use this tool to find multi-hop connections between genes, diseases, traits, and papers.
        """
        logger.info(f"Searching Knowledge Graph for: {query}")
        
        try:
            # 1. Semantic Search on Qdrant
            docs = await vector_store.asimilarity_search(query, k=top_k)
            
            if not docs:
                return "No relevant entities found in the knowledge graph."
                
            entity_ids = []
            for doc in docs:
                if "global_id" in doc.metadata:
                    entity_ids.append(doc.metadata["global_id"])
                    
            if not entity_ids:
                return "Found documents but no valid graph entities."

            # 2. Graph Retrieval from Neo4j
            # OPTIMIZATION: We use type(r) to get clean string names for relationships
            cypher_query = """
                MATCH (e)-[r1]-(n1)
                WHERE e.id IN $entity_ids
                OPTIONAL MATCH (n1)-[r2]-(n2)
                RETURN e, type(r1) AS r1_type, n1, type(r2) AS r2_type, n2
                LIMIT 50
            """

            # Use LangChain's built-in query execution
            records = knowledge_graph.query(cypher_query, params={"entity_ids": entity_ids})
                
            subgraph = []
            for record in records:
                # LangChain automatically parses nodes into dicts
                e_name = record.get("e", {}).get("name", "Unknown")
                rel1_type = record.get("r1_type") or "RELATED_TO"
                n1_name = record.get("n1", {}).get("name", "Unknown")
                
                subgraph.append(f"{e_name} -[{rel1_type}]-> {n1_name}")
                
                if record.get("r2_type") and record.get("n2"):
                    rel2_type = record.get("r2_type")
                    n2_name = record.get("n2", {}).get("name", "Unknown")
                    subgraph.append(f"{n1_name} -[{rel2_type}]-> {n2_name}")

            # 3. Format result
            if not subgraph:
                # Fallback to vector search results if no graph edges
                return "Found entities but no relationships: " + ", ".join([d.page_content for d in docs])
                
            # Deduplicate
            unique_edges = list(set(subgraph))
            formatted_context = "Knowledge Graph Context:\n" + "\n".join(unique_edges)
            return formatted_context

        except Exception as e:
            logger.error(f"GraphRAG Tool failed: {str(e)}")
            return f"Error retrieving knowledge graph context: {str(e)}"
    
    return search_knowledge_graph
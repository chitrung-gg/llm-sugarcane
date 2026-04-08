from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_qdrant import QdrantVectorStore
from loguru import logger

from app.configs.storage.databases import neo4j_driver


def make_graph_rag_tool(vector_store: QdrantVectorStore):
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
            # We query for 1-hop relationships from the retrieved entities.
            subgraph = []
            async with neo4j_driver.session() as session:
                # We use APOC or general match if we have many labels. Since we know labels, we can just match any node
                cypher_query = """
                    MATCH (e)-[r1]-(n1)
                    WHERE e.id IN $entity_ids
                    OPTIONAL MATCH (n1)-[r2]-(n2)
                    RETURN e, r1 AS r, n1 AS related, r2, n2
                    LIMIT 50
                """
                result = await session.run(cypher_query, entity_ids=entity_ids)
                records = await result.data()
                
                for record in records:
                    e_name = record["e"].get("name", "Unknown")
                    rel_type = record["r"][1] if record["r"] else "RELATED_TO"
                    related_name = record["related"].get("name", "Unknown")
                    
                    subgraph.append(f"{e_name} -[{rel_type}]-> {related_name}")
                    
                    if record["r2"] and record["n2"]:
                        r2_type = record["r2"][1] if record["r2"] else "RELATED_TO"
                        n2_name = record["n2"].get("name", "Unknown")
                        subgraph.append(f"{related_name} -[{r2_type}]-> {n2_name}")

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
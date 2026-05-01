from langchain_core.prompts import PromptTemplate

from langchain_core.prompts import PromptTemplate

EXTRACTION_PROMPT = PromptTemplate.from_template("""
    <role>
    You are a strict Biological Data Curator for a Sugarcane Knowledge Graph.
    Your job is to evaluate text and extract precise biological relationships into a JSON format.
    </role>

    <rules>
    1. RELEVANCE: If the text is NOT about plant biology, sugarcane (Saccharum), or genomics, you MUST set 'is_domain_relevant' to False and return empty arrays for nodes and edges.
    2. MISSING DATA: If the text indicates a failure, a 404 error, or missing data (e.g., "I was unable to retrieve..."), mark as not relevant.
    3. NODE LABELS: Permitted types are exactly: ["Gene", "Cultivar", "Paper", "Trait", "Disease", "Tissue", "Stress"].
    4. EDGE TYPES: Must be UPPERCASE strings (e.g., "UPREGULATES", "CAUSES", "RESISTS").
    5. CONFIDENCE: Provide an 'overall_confidence' score between 0.0 and 1.0.
    </rules>

    <text_to_analyze>
    {text}
    </text_to_analyze>

    <output_format>
    Return valid JSON matching this schema:
    {{
    "is_domain_relevant": boolean,
    "overall_confidence": float,
    "nodes": [ {{"id": string, "label": string, "properties": dict}} ],
    "edges": [ {{"source_id": string, "target_id": string, "type": string, "properties": dict}} ]
    }}
    </output_format>
""")
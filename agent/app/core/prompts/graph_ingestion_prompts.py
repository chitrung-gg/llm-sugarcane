from langchain_core.prompts import PromptTemplate
from app.schemas.graph.knowledge_graph_schema import KnowledgeGraphComponents, KnowledgeGraphNode, KnowledgeGraphRelationship

# 1. Define examples as Pydantic objects
_EX_EXTRACTION = KnowledgeGraphComponents(
    is_domain_relevant=True,
    overall_confidence=0.95,
    nodes=[
        KnowledgeGraphNode(
            name="ScDREB2",
            label="Gene",
            description="A transcription factor involved in drought stress response in sugarcane.",
            aliases=["Saccharum DREB2"]
        ),
        KnowledgeGraphNode(
            name="SP80-3280",
            label="Cultivar",
            description="A popular Brazilian sugarcane cultivar known for its high yield.",
            aliases=[]
        )
    ],
    relationships=[
        KnowledgeGraphRelationship(
            source_name="ScDREB2",
            target_name="SP80-3280",
            type="EXPRESSED_IN",
            evidence="ScDREB2 was found to be highly expressed in the Brazilian cultivar SP80-3280 during drought.",
            context="under drought stress",
            confidence=0.9
        )
    ]
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}
_FEW_SHOTS = f"""
<example name="biological_extraction">
  <ideal_response>
{_EX_EXTRACTION.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""

# ---------------------------------------------------------
# Single Extraction Prompt
# ---------------------------------------------------------
EXTRACTION_PROMPT_STR = """
You are the Lead Biological Data Curator for a Sugarcane Knowledge Graph. Your job is to read scientific text and extract precise biological entities and their relationships.

<text_to_analyze>
{text}
</text_to_analyze>

### Guidelines:
* **Relevance Check:** If the text is NOT about plant biology, sugarcane (Saccharum), or genomics—or if it's an error message (like "unable to retrieve")—simply mark it as irrelevant (`is_domain_relevant=False`) and leave nodes/relationships empty.
* **Node Categorization:** Categorize entities using standard labels like "Gene", "Cultivar", "Paper", "Trait", "Disease", "Tissue", or "Stress".
* **Relationship Naming:** Use clear, UPPERCASE action verbs for relationships (e.g., "UPREGULATES", "CAUSES", "RESISTS", "EXPRESSED_IN").
* **Confidence Scoring:** Assign a realistic `overall_confidence` score (0.0 to 1.0) based on how explicitly the relationships are stated in the text.

### Example Response:
{few_shots}
"""

EXTRACTION_PROMPT = PromptTemplate(
    template=EXTRACTION_PROMPT_STR,
    input_variables=["text"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)

# ---------------------------------------------------------
# Batch Extraction Prompt
# ---------------------------------------------------------
BATCH_EXTRACTION_PROMPT_STR = """
You are the Lead Biological Data Curator for a Sugarcane Knowledge Graph. Your job is to evaluate a batch of text chunks and extract precise biological relationships for EACH chunk.

<chunks_to_analyze>
{chunks}
</chunks_to_analyze>

### Guidelines:
* **Independent Analysis:** Treat each chunk as an isolated piece of data. Do not mix relationships, context, or entities between different chunks.
* **Strict Ordering:** You must process and return the exact same number of results as the input chunks, preserving the original array order.
* **Relevance Check:** If a specific chunk is not about plant biology, sugarcane, or genomics, mark its specific `is_domain_relevant` flag as False and leave its nodes/relationships empty.
* **Standardized Labels:** Use standard labels ("Gene", "Cultivar", "Trait", etc.) and UPPERCASE relationship types ("UPREGULATES", "EXPRESSED_IN", "INTERACTS_WITH").
"""

BATCH_EXTRACTION_PROMPT = PromptTemplate(
    template=BATCH_EXTRACTION_PROMPT_STR,
    input_variables=["chunks"]
)
import json
from langchain_core.prompts import PromptTemplate
from app.schemas.graph.knowledge_graph_schema import KnowledgeGraphComponents, BatchKnowledgeGraphComponents, KnowledgeGraphNode, KnowledgeGraphRelationship

# We generate the schema programmatically to ensure the prompt always stays in sync with the Pydantic model.
_EXTRACTION_SCHEMA = json.dumps(KnowledgeGraphComponents.model_json_schema(), indent=2)
_BATCH_EXTRACTION_SCHEMA = json.dumps(BatchKnowledgeGraphComponents.model_json_schema(), indent=2)

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
<example_scenario name="biological_extraction">
  <ideal_response>
{_EX_EXTRACTION.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example_scenario>
"""

EXTRACTION_PROMPT_STR = """
<role>
You are a strict Biological Data Curator for a Sugarcane Knowledge Graph.
Your job is to evaluate text and extract precise biological relationships into a JSON format.
</role>

<rules>
1. RELEVANCE: If the text is NOT about plant biology, sugarcane (Saccharum), or genomics, you MUST set 'is_domain_relevant' to False and return empty arrays for nodes and relationships.
2. MISSING DATA: If the text indicates a failure, a 404 error, or missing data (e.g., "I was unable to retrieve..."), mark as not relevant.
3. NODE LABELS: Permitted types are exactly: ["Gene", "Cultivar", "Paper", "Trait", "Disease", "Tissue", "Stress"].
4. RELATIONSHIP TYPES: Must be UPPERCASE strings (e.g., "UPREGULATES", "CAUSES", "RESISTS").
5. CONFIDENCE: Provide an 'overall_confidence' score between 0.0 and 1.0.
</rules>

<few_shot_scenarios>
{few_shots}
</few_shot_scenarios>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{extraction_schema}
</output_directive>

<text_to_analyze>
{text}
</text_to_analyze>
"""

EXTRACTION_PROMPT = PromptTemplate(
    template=EXTRACTION_PROMPT_STR,
    input_variables=["text"],
    partial_variables={
        "extraction_schema": _EXTRACTION_SCHEMA,
        "few_shots": _FEW_SHOTS
    }
)

BATCH_EXTRACTION_PROMPT_STR = """
<role>
You are a strict Biological Data Curator for a Sugarcane Knowledge Graph.
Your job is to evaluate a list of text chunks and extract precise biological relationships for EACH chunk.
</role>

<rules>
1. RELEVANCE: For each chunk, if it is NOT about plant biology, sugarcane, or genomics, set 'is_domain_relevant' to False for that specific result.
2. INDEPENDENCE: Treat each chunk as a separate entity. Do not mix data between chunks.
3. ORDER: You MUST return exactly the same number of results as input chunks, in the same order.
4. NODE LABELS: Permitted types: ["Gene", "Cultivar", "Paper", "Trait", "Disease", "Tissue", "Stress"].
</rules>

<output_directive>
You must respond with a JSON object that strictly follows this schema:
{batch_extraction_schema}
</output_directive>

<chunks_to_analyze>
{chunks}
</chunks_to_analyze>
"""

BATCH_EXTRACTION_PROMPT = PromptTemplate(
    template=BATCH_EXTRACTION_PROMPT_STR,
    input_variables=["chunks"],
    partial_variables={
        "batch_extraction_schema": _BATCH_EXTRACTION_SCHEMA
    }
)

from langchain_core.prompts import PromptTemplate
from app.schemas.graph.knowledge_graph_schema import KnowledgeGraphComponents, KnowledgeGraphNode, KnowledgeGraphRelationship

# 1. Define examples as Pydantic objects (Keep this exactly as you had it!)
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

# 2. The Heuristic-Driven System Prompt
EXTRACTION_PROMPT_STR = """
You are the Lead Biological Data Ontology Architect for a Sugarcane Knowledge Graph. Your job is to read scientific text and extract highly structured, atomic biological entities and their relational dynamics.

<text_to_analyze>
{text}
</text_to_analyze>

### Ontological Extraction Heuristics:
1. **Domain Gatekeeping (Signal vs. Noise):** If the text is NOT about plant biology, sugarcane, genetics, or agronomy (e.g., it is just methodology, software tools like "Bowtie2", or author names), mark it as irrelevant (`is_domain_relevant=False`) and leave nodes empty. We only map biological reality.
2. **Entity Atomicity (The Node Rule):** Nodes MUST be isolated nouns (e.g., "ScDREB2", "Smut", "R570"). NEVER extract clauses, adjectives, or full sentences as node names. 
3. **Ontological Categorization:** You must classify every node into one of these strict labels: `Gene`, `Protein`, `Cultivar`, `Species`, `Trait`, `Disease`, `Tissue`, `Chemical`, or `Environmental_Factor`.
4. **Directional Dynamics (The Edge Rule):** Relationships (`type`) must be clear, uppercase biological or physical verbs (e.g., "UPREGULATES", "EXPRESSED_IN", "CAUSES", "CONFERS_RESISTANCE_TO", "METABOLIZES"). The relationship must flow logically from the `source_name` to the `target_name`.
5. **Evidence Grounding:** The `evidence` field must contain the exact snippet or logical deduction from the text that proves this relationship exists. Set `confidence` based on how explicitly the text states this fact.

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
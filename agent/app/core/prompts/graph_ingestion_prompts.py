from langchain_core.prompts import PromptTemplate
from app.common.constants import GraphIngestionAllowedLabels
from app.schemas.graph.knowledge_graph_schema import KnowledgeGraphComponents, KnowledgeGraphNode, KnowledgeGraphRelationship

# Dynamically generate the string: "`Gene`, `Cultivar`, `Paper`, ..."
_ALLOWED_LABELS_STR = ", ".join([f"`{label.value}`" for label in GraphIngestionAllowedLabels])

# 1. Define examples as Pydantic objects (Keep this exactly as you had it!)
_EX_EXTRACTION = KnowledgeGraphComponents(
    is_domain_relevant=True,
    overall_confidence=0.95,
    nodes=[
        KnowledgeGraphNode(
            name="ScDREB2",
            label=GraphIngestionAllowedLabels.GENE,
            description="A transcription factor involved in drought stress response in sugarcane.",
            aliases=["Saccharum DREB2"]
        ),
        KnowledgeGraphNode(
            name="SP80-3280",
            label=GraphIngestionAllowedLabels.CULTIVAR,
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
1. **Domain Gatekeeping (Signal vs. Noise):** Mark as irrelevant (`is_domain_relevant=False`) ONLY IF the text is completely devoid of scientific value. Plant biology, sugarcane genetics, agronomy, AND bioinformatics methodologies (e.g., software tools like "Bowtie2", "CRISPOR", sequencing tech) ARE ALL highly relevant and must be processed. Reject ONLY pure boilerplate, publisher copyrights, author affiliations, or completely unrelated domains (e.g., financial news, human medicine).
2. **Entity Atomicity (The Node Rule):** Nodes MUST be isolated nouns (e.g., "ScDREB2", "Smut", "R570", "Bowtie2"). NEVER extract clauses, adjectives, or full sentences as node names. 
3. **Ontological Categorization:** You must strictly classify every node into ONE of the following approved labels: {allowed_labels}. Do not invent new labels.
4. **Directional Dynamics (The Edge Rule):** Relationships (`type`) must be clear, uppercase biological or physical verbs (e.g., "UPREGULATES", "EXPRESSED_IN", "ANALYZED_BY", "CONFERS_RESISTANCE_TO"). The relationship must flow logically from the `source_name` to the `target_name`.
5. **Evidence Grounding:** The `evidence` field must contain the exact snippet or logical deduction from the text that proves this relationship exists. Set `confidence` based on how explicitly the text states this fact.

### Example Response:
{few_shots}
"""

EXTRACTION_PROMPT = PromptTemplate(
    template=EXTRACTION_PROMPT_STR,
    input_variables=["text"],
    partial_variables={
        "few_shots": _FEW_SHOTS,
        "allowed_labels": _ALLOWED_LABELS_STR
    }
)
import json
from typing import List
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from app.schemas.agent.knowledge_graph import GraphPruningResult

_EX_PRUNED = GraphPruningResult(
    relevant_paths=[
        "(SCYLV) -[CAUSED_BY | Conf:1.0]-> (M. sacchari)",
        "(SCYLV) -[VECTORED_BY | Conf:0.9]-> (Rhopalosiphum maidis)"
    ]
)

_EX_EMPTY = GraphPruningResult(
    relevant_paths=[]
)

_JSON_OPTS = {"indent": 2, "exclude_none": True}

_FEW_SHOTS = f"""
<example name="successful_pruning">
  <reason>The user asked about aphid vectors for SCYLV. The raw graph returned plant cultivars, locations, and vectors. The model ruthlessly dropped the cultivars and kept ONLY the insect vectors.</reason>
  <user_query>Which aphid species are mentioned as vectors for the Sugarcane yellow leaf virus (SCYLV)?</user_query>
  <raw_graph_paths>
    (SCYLV) -[ASSOCIATED_WITH | Conf:0.9]-> (Saccharum spp.)
    (SCYLV) -[CAUSED_BY | Conf:1.0]-> (M. sacchari)
    (SCYLV) -[VECTORED_BY | Conf:0.9]-> (Rhopalosiphum maidis)
    (SCYLV) -[ASSOCIATED_WITH | Conf:0.8]-> (Guadeloupe)
  </raw_graph_paths>
  <ideal_response>
{_EX_PRUNED.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>

<example name="complete_rejection">
  <reason>The user asked for a genome size, but the graph only returned gene expression data. The model correctly returns an empty list to prevent hallucination.</reason>
  <user_query>What is the total sequence length of the R570 genome assembly?</user_query>
  <raw_graph_paths>
    (ScDREB2) -[EXPRESSED_IN | Conf:0.9]-> (Leaf Tissue)
    (ScDREB2) -[UPREGULATES | Conf:0.7]-> (Drought Tolerance)
  </raw_graph_paths>
  <ideal_response>
{_EX_EMPTY.model_dump_json(**_JSON_OPTS)}
  </ideal_response>
</example>
"""


GRAPH_PRUNING_PROMPT_STR = """
You are the Context Relevance Enforcer for a Sugarcane Knowledge Graph. Your job is to evaluate a list of raw graph relationships and strictly filter out the "noise" so downstream LLM agents only see data directly relevant to the user's question.

<user_query>
{user_query}
</user_query>

<raw_graph_paths>
{raw_paths}
</raw_graph_paths>

### Pruning Heuristics (Signal vs. Noise):
1. **Ruthless Elimination:** If a path does not contain nodes or relationship verbs that help answer the `<user_query>`, drop it immediately. Do not keep tangential information (e.g., if asked about insects, drop paths about plant varieties).
2. **Path Integrity:** When retaining a path, you MUST copy the string EXACTLY as it appears in `<raw_graph_paths>` (e.g., `(A) -[REL]-> (B)`). Do not alter names or confidence scores.
3. **Empty is Better than Wrong:** If NONE of the paths help answer the query, return an empty list `[]`. Downstream agents have fallback mechanisms for empty graphs; giving them irrelevant graph data will ruin their Contextual Relevancy scores.

### Example Responses:
{few_shots}
"""

GRAPH_PRUNING_PROMPT = PromptTemplate(
    template=GRAPH_PRUNING_PROMPT_STR,
    input_variables=["user_query", "raw_paths"],
    partial_variables={
        "few_shots": _FEW_SHOTS
    }
)
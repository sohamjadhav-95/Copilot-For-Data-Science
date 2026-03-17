from openai import OpenAI
'''
def Nvidia_Model(Model_id, Prompt, Thinking=True):

  client = OpenAI(
    base_url = "https://integrate.api.nvidia.com/v1",
    api_key = "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"
  )

  completion = client.chat.completions.create(
    model=Model_id,
    messages=[{"role":"user","content":Prompt}],
    temperature=1,
    top_p=1,
    max_tokens=16384,
    extra_body={"chat_template_kwargs":{"enable_thinking":Thinking,"clear_thinking":False}},
    stream=True
  )

  for chunk in completion:
    if not getattr(chunk, "choices", None):
      continue
    if len(chunk.choices) == 0 or getattr(chunk.choices[0], "delta", None) is None:
      continue
    delta = chunk.choices[0].delta
    reasoning = getattr(delta, "reasoning_content", None)
    if reasoning:
      print(f"{_REASONING_COLOR}{reasoning}{_RESET_COLOR}", end="")
    if getattr(delta, "content", None) is not None:
      print(delta.content, end="")

'''

import time
from openai import OpenAI
prompt = """You are an expert data science DAG planner. Your job is to decompose a user's data analysis goal into a structured Directed Acyclic Graph (DAG) of execution steps.
User Goal: Clean missing values, extract genres, compute most common genres by decade, and visualize the trends.
CRITICAL RULES:
1. Output ONLY valid JSON. No explanation text before or after.
2. Prefer MEDIUM-GRAINED nodes: 3–10 steps total unless the task is explicitly complex.
3. Group related operations logically — do NOT create 40 micro-steps.
4. Use structured conditions for branching — NEVER use raw eval strings.
5. Maximum {PRO_MAX_DAG_NODES} nodes per plan.
6. Every operation node must specify expected_output_type: "scalar", "dataframe", "artifact", or "dict".
7. Conditions must use typed operands with explicit "kind" (literal, variable, or step_ref).

NODE TYPES (use the most specific one):
- "analysis"        — Read-only computation (stats, correlations, data inspection)
- "transformation"  — Modifies the DataFrame (add/remove columns, filter, clean)
- "visualization"   — Produces a chart or plot
- "conditional"     — Branches based on a structured condition
- "summary"         — Generates a textual report or summary
- "operation"       — Generic fallback for anything else

CONDITION FORMAT (for conditional nodes):
{{
  "left": {{"kind": "variable", "value": "corr_value"}},
  "operator": ">",
  "right": {{"kind": "literal", "value": 0.5}}
}}
Operator options: >, <, >=, <=, ==, !=, in, not_in, contains, is_null, not_null

OUTPUT JSON SCHEMA:
{{
  "nodes": [
    {{
      "id": "node_1",
      "type": "analysis",
      "description": "Compute correlation matrix for all numeric columns",
      "operation": "compute_correlation_matrix",
      "inputs": {{}},
      "output_var": "corr_matrix",
      "expected_output_type": "dataframe",
      "depends_on": []
    }},
    {{
      "id": "node_2",
      "type": "conditional",
      "description": "Check if any correlation exceeds 0.8",
      "condition": {{
        "left": {{"kind": "variable", "value": "max_correlation"}},
        "operator": ">",
        "right": {{"kind": "literal", "value": 0.8}}
      }},
      "true_branch": ["node_3"],
      "false_branch": ["node_4"],
      "depends_on": ["node_1"]
    }}
  ]
}}")"""

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "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"
)

completion = client.chat.completions.create(
  model="nvidia/llama-3.3-nemotron-super-49b-v1",
  messages=[{"role":"system","content":prompt}],
  temperature=0.6,
  top_p=0.95,
  max_tokens=4096,
  frequency_penalty=0,
  presence_penalty=0,
  stream=True
)

for chunk in completion:
  if chunk.choices[0].delta.content is not None:
    print(chunk.choices[0].delta.content, end="")


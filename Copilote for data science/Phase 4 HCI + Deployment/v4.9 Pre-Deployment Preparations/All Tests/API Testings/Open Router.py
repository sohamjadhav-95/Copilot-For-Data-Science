import time
from openai import OpenAI

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key="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"
)

# Testing the Reasoning/Planning Model
prompt = """
Role: Senior Data Architect.
Task: Create a detailed 4-phase plan for an Automated Fraud Detection System.
Include: 
1. Real-time data ingestion strategy.
2. Feature engineering for 'behavioral anomalies'.
3. Model selection (XGBoost vs. Neural Networks).
4. A strategy for handling 'False Positives' in production.
Constraint: Format as a structured Markdown list with specific technical risks for each phase.
"""

start_time = time.time()
response = client.chat.completions.create(
  model="arcee-ai/trinity-large-preview:free",
  messages=[{"role": "user", "content": prompt}],
  stream=True
)

print("--- Trinity Large: Generating Plan ---\n")
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)

print(f"\n\n--- Total Time: {time.time() - start_time:.2f}s ---")
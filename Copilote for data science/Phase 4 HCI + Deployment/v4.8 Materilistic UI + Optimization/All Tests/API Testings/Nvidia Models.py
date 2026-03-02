from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "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"
)

completion = client.chat.completions.create(
  model="minimaxai/minimax-m2.5",
  messages=[{"role":"user","content":"What is meaning of life?"}],
  temperature=1,
  top_p=0.95,
  max_tokens=8192,
  stream=False
)

print(completion.choices[0].message.content)



from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "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"
)

completion = client.chat.completions.create(
  model="nvidia/nemotron-3-nano-30b-a3b",
  messages=[{"role":"user","content":"What is meaning of life?"}],
  temperature=0.15,
  top_p=0.95,
  max_tokens=8192,
  seed=42,
  extra_body={"chat_template_kwargs":{"enable_thinking":True,"clear_thinking":True}},
  stream=True
)

for chunk in completion:
  if chunk.choices and chunk.choices[0].delta.content is not None:
    print(chunk.choices[0].delta.content, end="")
  

